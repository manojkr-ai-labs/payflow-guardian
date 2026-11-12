from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, approval_stale, needs_checking, not_found, paypal_failed, validation_failed
from app.modules.activity.service import record
from app.modules.payments.models import Payment
from app.modules.payments.service import get_payment
from app.modules.paypal.types import CONFIRMED, NEEDS_CHECKING, PAYPAL_FAILED, UNCONFIRMED, PayPalAdapter, PayPalCall
from app.modules.refunds.models import OPEN_REFUND_STATUSES, RefundRequest


@dataclass
class PrepareOutcome:
    refund: RefundRequest
    payment: Payment
    created: bool


def payload_hash(
    *,
    payment_id: uuid.UUID,
    capture_id: str,
    amount_minor: int,
    currency: str,
    reason: str,
) -> str:
    parts = [str(payment_id), capture_id, str(amount_minor), currency, reason]
    material = "|".join(f"{len(part)}:{part}" for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def refund_payload(refund: RefundRequest) -> dict[str, object]:
    return {
        "id": str(refund.id),
        "payment_id": str(refund.payment_id),
        "capture_id": refund.capture_id,
        "amount_minor": refund.amount_minor,
        "currency": refund.currency,
        "reason": refund.reason,
        "payload_hash": refund.payload_hash,
        "status": refund.status,
        "prepared_by": str(refund.prepared_by),
        "approved_by": str(refund.approved_by) if refund.approved_by else None,
        "approved_at": _iso(refund.approved_at),
        "paypal_refund_id": refund.paypal_refund_id,
        "paypal_status": refund.paypal_status,
        "created_at": _iso(refund.created_at),
        "updated_at": _iso(refund.updated_at),
    }


def list_refunds(db: Session, merchant_id: uuid.UUID) -> list[RefundRequest]:
    rows = db.scalars(
        select(RefundRequest)
        .where(RefundRequest.merchant_id == merchant_id)
        .order_by(RefundRequest.created_at.desc(), RefundRequest.id.desc())
    )
    return list(rows)


def get_refund(db: Session, merchant_id: uuid.UUID, refund_id: uuid.UUID) -> RefundRequest:
    refund = db.scalar(
        select(RefundRequest).where(RefundRequest.id == refund_id, RefundRequest.merchant_id == merchant_id)
    )
    if refund is None:
        raise not_found("That refund was not found.")
    return refund


def _open_refund(db: Session, merchant_id: uuid.UUID, capture_id: str) -> RefundRequest | None:
    return db.scalar(
        select(RefundRequest).where(
            RefundRequest.merchant_id == merchant_id,
            RefundRequest.capture_id == capture_id,
            RefundRequest.status.in_(OPEN_REFUND_STATUSES),
        )
    )


def prepare_refund(
    db: Session,
    *,
    merchant_id: uuid.UUID,
    user_id: uuid.UUID,
    payment_id: uuid.UUID,
    amount_minor: int,
    currency: str,
    reason: str,
) -> PrepareOutcome:
    payment = get_payment(db, merchant_id, payment_id)
    capture_id = payment.paypal_capture_id
    if payment.status != "completed" or payment.confirmation != "confirmed" or not capture_id:
        raise validation_failed("The payment is not a confirmed capture.")
    existing = _open_refund(db, merchant_id, capture_id)
    if existing is not None:
        return PrepareOutcome(refund=existing, payment=payment, created=False)
    cleaned_reason = reason.strip()
    cleaned_currency = currency.strip().upper()
    if amount_minor <= 0 or amount_minor > payment.amount_minor:
        raise validation_failed("The refund amount must be greater than zero and no greater than the captured amount.")
    if cleaned_currency != payment.currency:
        raise validation_failed("The currency must match the payment.")
    if not cleaned_reason:
        raise validation_failed("A reason is required.")
    now = datetime.now(timezone.utc)
    refund = RefundRequest(
        merchant_id=merchant_id,
        payment_id=payment.id,
        capture_id=capture_id,
        amount_minor=amount_minor,
        currency=cleaned_currency,
        reason=cleaned_reason,
        payload_hash=payload_hash(
            payment_id=payment.id,
            capture_id=capture_id,
            amount_minor=amount_minor,
            currency=cleaned_currency,
            reason=cleaned_reason,
        ),
        status="pending_approval",
        prepared_by=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(refund)
    db.flush()
    record(
        db,
        merchant_id=merchant_id,
        actor_user_id=user_id,
        actor_type="user",
        action="refund.prepared",
        entity_type="refund",
        entity_id=refund.id,
        summary="A refund is waiting for approval.",
        outcome="confirmed",
        amount_minor=amount_minor,
        currency=cleaned_currency,
        paypal_reference=capture_id,
    )
    return PrepareOutcome(refund=refund, payment=payment, created=True)


@dataclass
class RefundOutcome:
    refund: RefundRequest
    error: AppError | None


def approve_refund(
    db: Session,
    *,
    merchant_id: uuid.UUID,
    user_id: uuid.UUID,
    refund_id: uuid.UUID,
    paypal: PayPalAdapter,
) -> RefundOutcome:
    refund = _refund_for_merchant(db, merchant_id, refund_id, lock=True)
    if refund is None:
        raise not_found("That refund was not found.")
    if refund.status in {"completed", "needs_checking", "failed"}:
        return RefundOutcome(refund=refund, error=None)
    if refund.status != "pending_approval":
        raise validation_failed("This refund is not waiting for approval.")
    payment = get_payment(db, merchant_id, refund.payment_id)
    _require_current_hash(refund, payment)
    now = datetime.now(timezone.utc)
    refund.approved_by = user_id
    refund.approved_at = now
    refund.approved_hash = refund.payload_hash
    refund.updated_at = now
    _record_refund(
        db,
        refund,
        user_id,
        action="refund.approved",
        outcome="confirmed",
        summary="The owner approved this refund.",
    )
    db.flush()
    try:
        call = paypal.refund_capture(refund.capture_id, refund.amount_minor, refund.currency, str(refund.id))
    except Exception:
        call = PayPalCall(
            operation="refund_capture",
            status=NEEDS_CHECKING,
            confirmation=UNCONFIRMED,
            error_code=NEEDS_CHECKING,
            message="PayPal did not answer. The refund needs a check.",
            paypal_capture_id=refund.capture_id,
        )
    kind = _apply_refund_result(refund, call)
    if kind == "completed":
        _record_refund(
            db,
            refund,
            user_id,
            action="refund.completed",
            outcome="confirmed",
            summary="PayPal confirmed the refund.",
        )
        error = None
    elif kind == "failed":
        _record_refund(
            db,
            refund,
            user_id,
            action="refund.failed",
            outcome="failed",
            summary="PayPal did not complete the refund.",
        )
        error = paypal_failed("PayPal did not complete the refund.")
    else:
        _record_refund(
            db,
            refund,
            user_id,
            action="refund.needs_checking",
            outcome="needs_checking",
            summary="The refund needs a check.",
        )
        error = needs_checking("PayPal has not confirmed this refund. It needs a check.")
    db.flush()
    return RefundOutcome(refund=refund, error=error)


def reject_refund(
    db: Session,
    *,
    merchant_id: uuid.UUID,
    user_id: uuid.UUID,
    refund_id: uuid.UUID,
) -> RefundRequest:
    refund = _refund_for_merchant(db, merchant_id, refund_id, lock=True)
    if refund is None:
        raise not_found("That refund was not found.")
    if refund.status == "rejected":
        return refund
    if refund.status == "completed":
        raise validation_failed("A completed refund cannot be rejected.")
    refund.status = "rejected"
    refund.updated_at = datetime.now(timezone.utc)
    _record_refund(
        db,
        refund,
        user_id,
        action="refund.rejected",
        outcome="rejected",
        summary="The refund was rejected.",
    )
    db.flush()
    return refund


def _refund_for_merchant(
    db: Session,
    merchant_id: uuid.UUID,
    refund_id: uuid.UUID,
    *,
    lock: bool,
) -> RefundRequest | None:
    stmt = select(RefundRequest).where(RefundRequest.id == refund_id, RefundRequest.merchant_id == merchant_id)
    bind = db.get_bind()
    if lock and bind is not None and bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def _require_current_hash(refund: RefundRequest, payment: Payment) -> None:
    capture_id = payment.paypal_capture_id or ""
    current = payload_hash(
        payment_id=payment.id,
        capture_id=capture_id,
        amount_minor=refund.amount_minor,
        currency=refund.currency,
        reason=refund.reason,
    )
    stale = (
        current != refund.payload_hash
        or capture_id != refund.capture_id
        or refund.currency != payment.currency
        or refund.amount_minor <= 0
        or refund.amount_minor > payment.amount_minor
        or payment.status != "completed"
        or payment.confirmation != "confirmed"
    )
    if stale:
        raise approval_stale("The refund request changed. Approve the current request again.")


def _apply_refund_result(refund: RefundRequest, call: PayPalCall) -> str:
    refund.updated_at = datetime.now(timezone.utc)
    refund.paypal_status = _clean_status(call.paypal_status)
    paypal_refund_id = _clean_id(call.paypal_refund_id)
    explicit = call.error_code == PAYPAL_FAILED or (call.status == "failed" and call.confirmation == CONFIRMED)
    if explicit:
        if paypal_refund_id is not None:
            refund.paypal_refund_id = paypal_refund_id
        refund.status = "failed"
        return "failed"
    if call.confirmation == CONFIRMED and call.error_code is None and call.status == "completed" and paypal_refund_id:
        refund.paypal_refund_id = paypal_refund_id
        refund.status = "completed"
        return "completed"
    refund.status = "needs_checking"
    return "needs_checking"


def _record_refund(
    db: Session,
    refund: RefundRequest,
    user_id: uuid.UUID,
    *,
    action: str,
    outcome: str,
    summary: str,
) -> None:
    reference = refund.paypal_refund_id or refund.capture_id
    record(
        db,
        merchant_id=refund.merchant_id,
        actor_user_id=user_id,
        actor_type="user",
        action=action,
        entity_type="refund",
        entity_id=refund.id,
        summary=summary,
        outcome=outcome,
        amount_minor=refund.amount_minor,
        currency=refund.currency,
        paypal_reference=reference,
    )


def _clean_id(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 64:
        return None
    return cleaned


def _clean_status(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 64:
        return None
    return cleaned
