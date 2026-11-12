from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, needs_checking, not_found, paypal_failed, validation_failed
from app.modules.activity.service import record
from app.modules.catalog.orders import TestOrder, get_test_order
from app.modules.payments.models import Order, Payment
from app.modules.paypal.money import minor_to_paypal
from app.modules.paypal.status import confirm_payment_status
from app.modules.paypal.types import CONFIRMED, NEEDS_CHECKING, PAYPAL_FAILED, UNCONFIRMED, PayPalAdapter, PayPalCall

logger = logging.getLogger("app.payments")

_SUCCESS_STATUSES = frozenset({"awaiting_payer", "created"})
_SECRET_MARKERS = ("bearer ", "client_secret", "access_token", "api_key", "authorization")
_PAYPAL_ID_LIMIT = 64


@dataclass
class CreateOutcome:
    payment: Payment
    error: AppError | None
    inserted: bool


def normalize_idempotency_key(value: str | None) -> str:
    if value is None or not value.strip():
        raise validation_failed("An Idempotency-Key header is required.")
    key = value.strip()
    if len(key) > 128 or any(ord(char) < 32 or ord(char) > 126 for char in key):
        raise validation_failed("The idempotency key is not valid.")
    return key


def payment_payload(payment: Payment) -> dict[str, object]:
    order = payment.order
    item = get_test_order(order.test_order_code)
    created_at = payment.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        "id": str(payment.id),
        "order_id": str(order.id),
        "test_order_code": order.test_order_code,
        "description": item.description if item else order.test_order_code,
        "amount_minor": payment.amount_minor,
        "display_amount": minor_to_paypal(payment.amount_minor, payment.currency),
        "currency": payment.currency,
        "status": payment.status,
        "confirmation": payment.confirmation,
        "paypal_order_id": payment.paypal_order_id,
        "paypal_capture_id": payment.paypal_capture_id,
        "paypal_status": payment.paypal_status,
        "approve_url": payment.approve_url,
        "created_at": created_at.isoformat(),
        "updated_at": _iso_timestamp(payment.updated_at),
        "last_checked_at": _iso_timestamp(payment.last_checked_at) if payment.last_checked_at else None,
        "fact_sheet": _load_fact_sheet(payment),
    }


def _iso_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def payment_list_item(payment: Payment) -> dict[str, object]:
    return {
        "id": str(payment.id),
        "status": payment.status,
        "confirmation": payment.confirmation,
        "amount_minor": payment.amount_minor,
        "currency": payment.currency,
        "paypal_order_id": payment.paypal_order_id,
        "paypal_capture_id": payment.paypal_capture_id,
        "paypal_status": payment.paypal_status,
        "created_at": _iso_timestamp(payment.created_at),
        "updated_at": _iso_timestamp(payment.updated_at),
        "test_order_code": payment.order.test_order_code,
    }


def create_test_payment(
    db: Session,
    *,
    merchant_id: uuid.UUID,
    user_id: uuid.UUID,
    test_order_code: str,
    idempotency_key: str | None,
    paypal: PayPalAdapter,
    web_origin: str,
) -> CreateOutcome:
    key = normalize_idempotency_key(idempotency_key)
    item = get_test_order(test_order_code)
    if item is None:
        raise validation_failed("That test order is not in the catalog.")

    existing = _find(db, merchant_id, key)
    if existing is not None:
        _require_same_code(existing, item.code)
        return CreateOutcome(payment=existing, error=_error_for_stored(existing), inserted=False)

    now = datetime.now(timezone.utc)
    order = Order(
        merchant_id=merchant_id,
        test_order_code=item.code,
        amount_minor=item.amount_minor,
        currency=item.currency,
        status="created",
        created_by=user_id,
        created_at=now,
    )
    payment = Payment(
        merchant_id=merchant_id,
        order=order,
        idempotency_key=key,
        status="created",
        confirmation=UNCONFIRMED,
        amount_minor=item.amount_minor,
        currency=item.currency,
        created_at=now,
        updated_at=now,
    )
    try:
        with db.begin_nested():
            db.add(order)
            db.add(payment)
            db.flush()
    except IntegrityError:
        existing = _find(db, merchant_id, key)
        if existing is None:
            raise validation_failed("The test order could not be saved. Try again.") from None
        _require_same_code(existing, item.code)
        return CreateOutcome(payment=existing, error=_error_for_stored(existing), inserted=False)

    origin = web_origin.strip().rstrip("/")
    try:
        call = paypal.create_order(
            item.amount_minor,
            item.currency,
            f"{origin}/payments/{payment.id}/return",
            f"{origin}/payments/{payment.id}/cancel",
        )
    except Exception:
        logger.info("payment create paypal_order_id= outcome=needs_checking")
        call = PayPalCall(
            operation="create_order",
            status=NEEDS_CHECKING,
            confirmation=UNCONFIRMED,
            error_code=NEEDS_CHECKING,
            message="PayPal did not answer. The payment needs a check.",
        )

    error = _apply_paypal_result(payment, order, item, call)
    _record_created(db, payment, user_id, item)
    db.flush()
    logger.info(
        "payment.created id=%s status=%s paypal_order_id=%s",
        payment.id,
        payment.status,
        payment.paypal_order_id or "",
    )
    return CreateOutcome(payment=payment, error=error, inserted=True)


@dataclass
class CaptureOutcome:
    payment: Payment
    error: AppError | None


def get_payment(db: Session, merchant_id: uuid.UUID, payment_id: uuid.UUID) -> Payment:
    payment = _payment_for_merchant(db, merchant_id, payment_id, lock=False)
    if payment is None:
        raise not_found("That payment was not found.")
    return payment


def list_payments(
    db: Session,
    merchant_id: uuid.UUID,
    *,
    q: str | None = None,
    status: str | None = None,
) -> list[Payment]:
    stmt = (
        select(Payment)
        .options(joinedload(Payment.order, innerjoin=True))
        .where(Payment.merchant_id == merchant_id)
    )
    status_filter = _status_filter(status)
    if status_filter is not None:
        stmt = stmt.where(status_filter)
    query_filter = _query_filter(q)
    if query_filter is not None:
        stmt = stmt.where(query_filter)
    rows = db.scalars(stmt.order_by(Payment.created_at.desc(), Payment.id.desc())).unique()
    return list(rows)


def investigate_payment(
    db: Session,
    *,
    merchant_id: uuid.UUID,
    user_id: uuid.UUID,
    payment_id: uuid.UUID,
    paypal: PayPalAdapter,
) -> Payment:
    payment = _payment_for_merchant(db, merchant_id, payment_id, lock=False)
    if payment is None:
        raise not_found("That payment was not found.")
    try:
        call = paypal.get_order_or_capture(
            paypal_order_id=payment.paypal_order_id,
            paypal_capture_id=payment.paypal_capture_id,
        )
    except Exception:
        logger.info("payment investigate id=%s outcome=needs_checking", payment.id)
        _store_incomplete_refresh(db, payment, user_id)
        return payment

    paypal_status = _clean_status(call.paypal_status)
    if paypal_status is None:
        _store_incomplete_refresh(db, payment, user_id)
        return payment

    now = datetime.now(timezone.utc)
    capture_id = _clean_paypal_id(call.paypal_capture_id) or payment.paypal_capture_id
    order_id = _clean_paypal_id(call.paypal_order_id) or payment.paypal_order_id
    local, confirmation = confirm_payment_status(paypal_status, order_id=order_id, capture_id=capture_id)
    fresh_capture = _clean_paypal_id(call.paypal_capture_id)
    fresh_currency = call.currency.strip().upper() if isinstance(call.currency, str) and call.currency.strip() else None
    mismatch = _paypal_mismatch(
        payment,
        local=local,
        confirmation=confirmation,
        fresh_capture=fresh_capture,
        fresh_amount=call.amount_minor,
        fresh_currency=fresh_currency,
    )
    payment.last_checked_at = now
    payment.updated_at = now
    payment.paypal_status = paypal_status
    if mismatch:
        payment.status = NEEDS_CHECKING
        payment.confirmation = UNCONFIRMED
        payment.order.status = NEEDS_CHECKING
        payment.fact_sheet = json.dumps(
            _fact_sheet(payment, missing=[], checked_at=now, paypal_status=paypal_status, mismatch=True)
        )
        _record_mismatch(db, payment, user_id)
        db.flush()
        return payment
    if confirmation != CONFIRMED:
        payment.status = NEEDS_CHECKING
        payment.confirmation = UNCONFIRMED
        payment.order.status = NEEDS_CHECKING
        outcome = "needs_checking"
    else:
        payment.status = local
        payment.confirmation = CONFIRMED
        payment.order.status = local
        if payment.paypal_capture_id is None and _clean_paypal_id(call.paypal_capture_id):
            payment.paypal_capture_id = _clean_paypal_id(call.paypal_capture_id)
        outcome = "confirmed"
    payment.fact_sheet = json.dumps(_fact_sheet(payment, missing=[], checked_at=now, paypal_status=paypal_status))
    _record_investigated(db, payment, user_id, outcome, completed=True)
    db.flush()
    return payment


def capture_payment(
    db: Session,
    *,
    merchant_id: uuid.UUID,
    user_id: uuid.UUID,
    payment_id: uuid.UUID,
    paypal: PayPalAdapter,
) -> CaptureOutcome:
    payment = _payment_for_merchant(db, merchant_id, payment_id, lock=True)
    if payment is None:
        raise not_found("That payment was not found.")
    if payment.paypal_capture_id and payment.confirmation == CONFIRMED:
        return CaptureOutcome(payment=payment, error=None)

    order_id = payment.paypal_order_id
    if not order_id:
        _store_needs_checking(payment)
        _record_capture(db, payment, user_id, "needs_checking")
        db.flush()
        return CaptureOutcome(payment=payment, error=needs_checking("PayPal has not confirmed this payment. It needs a check."))

    try:
        call = paypal.capture_order(order_id)
    except Exception:
        logger.info("payment capture paypal_order_id=%s outcome=needs_checking", order_id)
        call = PayPalCall(
            operation="capture_order",
            status=NEEDS_CHECKING,
            confirmation=UNCONFIRMED,
            error_code=NEEDS_CHECKING,
            message="PayPal did not answer. The payment needs a check.",
            paypal_order_id=order_id,
        )

    error = _apply_capture_result(payment, call)
    if error is None:
        kind = "captured"
    elif error.code == "paypal_failed":
        kind = "failed"
    else:
        kind = "needs_checking"
    _record_capture(db, payment, user_id, kind)
    db.flush()
    logger.info(
        "payment.capture id=%s status=%s paypal_capture_id=%s",
        payment.id,
        payment.status,
        payment.paypal_capture_id or "",
    )
    return CaptureOutcome(payment=payment, error=error)


def _payment_for_merchant(
    db: Session,
    merchant_id: uuid.UUID,
    payment_id: uuid.UUID,
    *,
    lock: bool,
) -> Payment | None:
    stmt = (
        select(Payment)
        .options(joinedload(Payment.order, innerjoin=True))
        .where(Payment.merchant_id == merchant_id, Payment.id == payment_id)
    )
    bind = db.get_bind()
    if lock and bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def _apply_capture_result(payment: Payment, call: PayPalCall) -> AppError | None:
    payment.updated_at = datetime.now(timezone.utc)
    payment.paypal_status = _clean_status(call.paypal_status)
    capture_id = _clean_paypal_id(call.paypal_capture_id)
    local, confirmation = confirm_payment_status(
        call.paypal_status,
        order_id=payment.paypal_order_id,
        capture_id=capture_id,
    )
    explicit = call.error_code == PAYPAL_FAILED or call.status == "failed" or local == "failed"
    if explicit and local == "failed" and confirmation == CONFIRMED:
        if capture_id is not None:
            payment.paypal_capture_id = capture_id
        payment.status = "failed"
        payment.confirmation = CONFIRMED
        payment.order.status = "failed"
        _remember_capture_sheet(payment)
        return paypal_failed(_public_capture_failure(call))

    if (
        not explicit
        and confirmation == CONFIRMED
        and local == "completed"
        and capture_id is not None
        and call.error_code is None
    ):
        payment.paypal_capture_id = capture_id
        payment.status = "completed"
        payment.confirmation = CONFIRMED
        payment.order.status = "completed"
        _remember_capture_sheet(payment)
        return None

    _store_needs_checking(payment)
    return needs_checking("PayPal has not confirmed this payment. It needs a check.")


def _remember_capture_sheet(payment: Payment) -> None:
    """Keep the PayPal fact sheet aligned with a capture that changed the payment."""
    payment.last_checked_at = payment.updated_at
    payment.fact_sheet = json.dumps(
        _fact_sheet(payment, missing=[], checked_at=payment.updated_at, paypal_status=payment.paypal_status)
    )


def _store_needs_checking(payment: Payment) -> None:
    payment.updated_at = datetime.now(timezone.utc)
    payment.status = NEEDS_CHECKING
    payment.confirmation = UNCONFIRMED
    payment.order.status = NEEDS_CHECKING


def _record_capture(db: Session, payment: Payment, user_id: uuid.UUID, kind: str) -> None:
    reference = payment.paypal_capture_id or payment.paypal_order_id
    if reference is not None and len(reference) > _PAYPAL_ID_LIMIT:
        reference = None
    if kind == "failed":
        action = "payment.captured"
        outcome = "failed"
        summary = "PayPal did not capture the payment."
    elif kind == "needs_checking":
        action = "payment.needs_checking"
        outcome = "needs_checking"
        summary = "The payment needs a check before it can be confirmed."
    else:
        action = "payment.captured"
        outcome = "confirmed"
        summary = f"Captured {payment.amount_minor} {payment.currency}."
        if reference:
            summary = f"Captured payment. PayPal reference {reference}."
    record(
        db,
        merchant_id=payment.merchant_id,
        actor_user_id=user_id,
        actor_type="user",
        action=action,
        entity_type="payment",
        entity_id=payment.id,
        summary=summary,
        outcome=outcome,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        paypal_reference=reference,
    )


def _public_capture_failure(call: PayPalCall) -> str:
    message = " ".join((call.message or "").split())
    lowered = message.lower()
    if not message or any(marker in lowered for marker in _SECRET_MARKERS):
        return "PayPal did not capture the payment."
    return message[:240]


def _status_filter(status: str | None):
    if status is None or not status.strip():
        return None
    normalized = status.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized == "pending":
        return Payment.status.in_(("awaiting_payer", "pending"))
    if normalized == "refunded":
        return Payment.status.in_(("refunded", "partially_refunded"))
    return Payment.status == normalized


def _query_filter(q: str | None):
    if q is None or not q.strip():
        return None
    term = q.strip()
    clauses = [Payment.paypal_order_id == term, Payment.paypal_capture_id == term]
    try:
        clauses.append(Payment.id == uuid.UUID(term))
    except ValueError:
        pass
    return or_(*clauses)


def _load_fact_sheet(payment: Payment) -> dict[str, object] | None:
    if not payment.fact_sheet:
        return None
    try:
        parsed = json.loads(payment.fact_sheet)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _fact_sheet(
    payment: Payment,
    *,
    missing: list[str],
    checked_at: datetime | None,
    paypal_status: str | None,
    mismatch: bool = False,
) -> dict[str, object]:
    return {
        "payment_id": str(payment.id),
        "paypal_order_id": payment.paypal_order_id,
        "paypal_capture_id": payment.paypal_capture_id,
        "paypal_status": paypal_status,
        "local_status": payment.status,
        "confirmation": payment.confirmation,
        "amount": minor_to_paypal(payment.amount_minor, payment.currency),
        "currency": payment.currency,
        "missing": missing,
        "checked_at": _iso_timestamp(checked_at) if checked_at else None,
        "mismatch": mismatch,
    }


def _store_incomplete_refresh(db: Session, payment: Payment, user_id: uuid.UUID) -> None:
    payment.fact_sheet = json.dumps(
        _fact_sheet(
            payment,
            missing=["paypal_status", "paypal_order_id", "paypal_capture_id"],
            checked_at=payment.last_checked_at,
            paypal_status=None,
        )
    )
    _record_investigated(db, payment, user_id, "needs_checking", completed=False)
    db.flush()


def _paypal_mismatch(
    payment: Payment,
    *,
    local: str,
    confirmation: str,
    fresh_capture: str | None,
    fresh_amount: int | None,
    fresh_currency: str | None,
) -> bool:
    if fresh_amount is not None and fresh_amount != payment.amount_minor:
        return True
    if fresh_currency is not None and fresh_currency != payment.currency:
        return True
    if fresh_capture and payment.paypal_capture_id and fresh_capture != payment.paypal_capture_id:
        return True
    return confirmation == CONFIRMED and local != payment.status


def _record_mismatch(db: Session, payment: Payment, user_id: uuid.UUID) -> None:
    reference = payment.paypal_capture_id or payment.paypal_order_id
    if reference is not None and len(reference) > _PAYPAL_ID_LIMIT:
        reference = None
    record(
        db,
        merchant_id=payment.merchant_id,
        actor_user_id=user_id,
        actor_type="user",
        action="payment.mismatch",
        entity_type="payment",
        entity_id=payment.id,
        summary="The saved payment and the latest PayPal data differ.",
        outcome="needs_checking",
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        paypal_reference=reference,
    )


def _record_investigated(db: Session, payment: Payment, user_id: uuid.UUID, outcome: str, *, completed: bool) -> None:
    reference = payment.paypal_capture_id or payment.paypal_order_id
    if reference is not None and len(reference) > _PAYPAL_ID_LIMIT:
        reference = None
    if completed and outcome == "confirmed":
        summary = "Refreshed the payment from PayPal."
    elif outcome == "needs_checking" and payment.status == NEEDS_CHECKING and payment.confirmation == UNCONFIRMED and completed:
        summary = "PayPal returned a status that needs a check."
    else:
        summary = "The PayPal refresh did not complete."
    record(
        db,
        merchant_id=payment.merchant_id,
        actor_user_id=user_id,
        actor_type="user",
        action="payment.investigated",
        entity_type="payment",
        entity_id=payment.id,
        summary=summary,
        outcome=outcome,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        paypal_reference=reference,
    )


def _find(db: Session, merchant_id: uuid.UUID, key: str) -> Payment | None:
    return db.scalar(
        select(Payment)
        .options(joinedload(Payment.order))
        .where(Payment.merchant_id == merchant_id, Payment.idempotency_key == key)
    )


def _require_same_code(payment: Payment, code: str) -> None:
    if payment.order.test_order_code != code:
        raise validation_failed("This idempotency key was already used for a different test order.")


def _apply_paypal_result(payment: Payment, order: Order, item: TestOrder, call: PayPalCall) -> AppError | None:
    payment.updated_at = datetime.now(timezone.utc)
    payment.paypal_status = _clean_status(call.paypal_status)
    paypal_order_id = _clean_paypal_id(call.paypal_order_id)
    if paypal_order_id is not None:
        payment.paypal_order_id = paypal_order_id

    approve_url = _clean_approve_url(call.approve_url)
    kind = _classify(call, item, paypal_order_id, approve_url)
    if kind == "created":
        payment.status = call.status
        payment.confirmation = CONFIRMED
        payment.approve_url = approve_url
        order.status = call.status
        return None

    payment.approve_url = None
    if kind == "failed":
        recognized_failure = call.confirmation == CONFIRMED and paypal_order_id and not _money_mismatch(call, item)
        payment.status = "failed"
        payment.confirmation = CONFIRMED if recognized_failure else UNCONFIRMED
        order.status = "failed"
        return paypal_failed(_public_failure_message(call))

    payment.status = NEEDS_CHECKING
    payment.confirmation = UNCONFIRMED
    order.status = NEEDS_CHECKING
    return needs_checking("PayPal has not confirmed this order. It needs a check.")


def _classify(call: PayPalCall, item: TestOrder, paypal_order_id: str | None, approve_url: str | None) -> str:
    mismatch = _money_mismatch(call, item)
    explicit = call.error_code == PAYPAL_FAILED or call.status == "failed"
    if explicit and not (mismatch and paypal_order_id):
        return "failed"
    if (
        not mismatch
        and call.confirmation == CONFIRMED
        and call.error_code is None
        and call.status in _SUCCESS_STATUSES
        and paypal_order_id
        and approve_url
    ):
        return "created"
    return "needs_checking"


def _money_mismatch(call: PayPalCall, item: TestOrder) -> bool:
    if call.amount_minor is not None and call.amount_minor != item.amount_minor:
        return True
    if call.currency is not None and call.currency.strip().upper() != item.currency:
        return True
    return False


def _error_for_stored(payment: Payment) -> AppError | None:
    if payment.status == "failed":
        return paypal_failed("PayPal did not create the order.")
    if (
        payment.status in _SUCCESS_STATUSES
        and payment.confirmation == CONFIRMED
        and payment.paypal_order_id
        and payment.approve_url
    ):
        return None
    return needs_checking("PayPal has not confirmed this order. It needs a check.")


def _record_created(db: Session, payment: Payment, user_id: uuid.UUID, item: TestOrder) -> None:
    reference = payment.paypal_order_id if payment.paypal_order_id and len(payment.paypal_order_id) <= _PAYPAL_ID_LIMIT else None
    if payment.status == "failed":
        outcome = "failed"
        summary = f"PayPal did not create test order {item.code}."
    elif payment.status == NEEDS_CHECKING or payment.confirmation != CONFIRMED:
        outcome = "needs_checking"
        summary = f"Test order {item.code} needs a check before it can continue."
    else:
        outcome = "confirmed"
        summary = f"Created test order {item.code} for {item.display_amount} {item.currency}."
        if reference:
            summary = f"{summary} PayPal reference {reference}."
    record(
        db,
        merchant_id=payment.merchant_id,
        actor_user_id=user_id,
        actor_type="user",
        action="payment.created",
        entity_type="payment",
        entity_id=payment.id,
        summary=summary,
        outcome=outcome,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        paypal_reference=reference,
    )


def _public_failure_message(call: PayPalCall) -> str:
    message = " ".join((call.message or "").split())
    lowered = message.lower()
    if not message or any(marker in lowered for marker in _SECRET_MARKERS):
        return "PayPal did not create the order."
    return message[:240]


def _clean_paypal_id(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > _PAYPAL_ID_LIMIT:
        return None
    return cleaned


def _clean_approve_url(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if len(cleaned) > 2048:
        return None
    if not cleaned.startswith("https://") and not cleaned.startswith("http://"):
        return None
    return cleaned


def _clean_status(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 64:
        return None
    return cleaned
