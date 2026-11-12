from sqlalchemy import select

from app.modules.activity.models import ActivityEvent
from app.modules.activity.service import record
from app.modules.auth.models import Merchant


def test_record_uses_the_caller_transaction(db) -> None:
    merchant = db.scalar(select(Merchant))
    record(
        db,
        merchant_id=merchant.id,
        action="payment.created",
        entity_type="payment",
        summary="Test example payment recorded.",
        outcome="confirmed",
        actor_type="system",
        amount_minor=2500,
        currency="USD",
        paypal_reference="ORDER-1",
    )
    db.commit()
    stored = db.scalar(select(ActivityEvent).where(ActivityEvent.paypal_reference == "ORDER-1"))
    assert stored.amount_minor == 2500
    assert stored.currency == "USD"
    assert stored.summary == "Test example payment recorded."
    assert "client_secret" not in stored.summary

    record(
        db,
        merchant_id=merchant.id,
        action="payment.needs_checking",
        entity_type="payment",
        summary="This event should roll back.",
        outcome="needs_checking",
        actor_type="system",
    )
    db.rollback()
    leftovers = db.scalars(select(ActivityEvent).where(ActivityEvent.summary == "This event should roll back.")).all()
    assert leftovers == []
