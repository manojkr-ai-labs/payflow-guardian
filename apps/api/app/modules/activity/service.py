from __future__ import annotations

import uuid

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.activity.models import ACTOR_TYPES, OUTCOMES, ActivityEvent


def record(
    db: Session,
    *,
    merchant_id: uuid.UUID,
    action: str,
    entity_type: str,
    summary: str,
    outcome: str,
    actor_type: str,
    entity_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    amount_minor: int | None = None,
    currency: str | None = None,
    paypal_reference: str | None = None,
) -> ActivityEvent:
    if actor_type not in ACTOR_TYPES:
        raise ValueError(f"Unknown actor_type: {actor_type}")
    if outcome not in OUTCOMES:
        raise ValueError(f"Unknown outcome: {outcome}")
    event = ActivityEvent(
        merchant_id=merchant_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        outcome=outcome,
        amount_minor=amount_minor,
        currency=currency,
        paypal_reference=paypal_reference,
    )
    db.add(event)
    db.flush()
    return event


def list_activity(db: Session, merchant_id: uuid.UUID, *, limit: int = 50) -> list[ActivityEvent]:
    rows = db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.merchant_id == merchant_id)
        .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
        .limit(limit)
    )
    return list(rows)


def activity_payload(event: ActivityEvent) -> dict[str, object]:
    created_at = event.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        "action": event.action,
        "summary": event.summary,
        "outcome": event.outcome,
        "amount_minor": event.amount_minor,
        "currency": event.currency,
        "paypal_reference": event.paypal_reference,
        "actor_type": event.actor_type,
        "created_at": created_at.isoformat(),
    }
