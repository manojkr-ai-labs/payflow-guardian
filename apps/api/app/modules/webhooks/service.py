"""Apply a verified PayPal webhook to an existing payment. It does not capture or refund."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.modules.activity.service import record
from app.modules.payments.models import Payment
from app.modules.paypal.status import map_paypal_status
from app.modules.paypal.types import CONFIRMED
from app.modules.paypal.webhooks import verify_webhook
from app.modules.webhooks.models import PayPalEvent


def apply_webhook(db: Session, *, body: bytes, headers: dict[str, str], webhook_id: str) -> None:
    if not verify_webhook(body=body, headers=headers, webhook_id=webhook_id):
        return
    payload = _object(body)
    if payload is None:
        return
    event_id = _event_id(payload.get("id"))
    if event_id is None:
        return
    if db.scalar(select(PayPalEvent.id).where(PayPalEvent.paypal_event_id == event_id)) is not None:
        return
    db.add(PayPalEvent(paypal_event_id=event_id, created_at=datetime.now(timezone.utc)))
    db.flush()
    resource = payload.get("resource")
    if not isinstance(resource, dict):
        return
    paypal_status = resource.get("status")
    if not isinstance(paypal_status, str):
        return
    paypal_id = _reference(resource.get("id"))
    if paypal_id is None:
        return
    payment = _payment_for_reference(db, paypal_id)
    if payment is None:
        return
    local, confirmation = map_paypal_status(paypal_status, paypal_id=paypal_id)
    now = datetime.now(timezone.utc)
    payment.status = local
    payment.confirmation = confirmation
    payment.paypal_status = paypal_status.strip()[:64]
    payment.updated_at = now
    payment.order.status = local
    if confirmation == CONFIRMED and local == "failed":
        outcome = "failed"
    elif confirmation == CONFIRMED:
        outcome = "confirmed"
    else:
        outcome = "needs_checking"
    record(
        db,
        merchant_id=payment.merchant_id,
        actor_type="paypal",
        action="payment.webhook",
        entity_type="payment",
        entity_id=payment.id,
        summary=f"PayPal reported {payment.paypal_status} for {paypal_id}.",
        outcome=outcome,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        paypal_reference=paypal_id,
    )


def _object(body: bytes) -> dict[str, object] | None:
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def _event_id(value: object) -> str | None:
    return _reference(value)


def _reference(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 64:
        return None
    return cleaned


def _payment_for_reference(db: Session, paypal_id: str) -> Payment | None:
    return db.scalar(
        select(Payment)
        .options(joinedload(Payment.order))
        .where(or_(Payment.paypal_order_id == paypal_id, Payment.paypal_capture_id == paypal_id))
    )
