import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.db import Base, get_engine, get_session_factory
from app.main import create_app
from app.modules.activity.models import ActivityEvent
from app.modules.auth.models import Membership
from app.modules.auth.seed import seed_demo
from app.modules.payments.models import Order, Payment
from app.modules.webhooks import models as webhook_models  # noqa: F401
from app.modules.webhooks.models import PayPalEvent


def _payment() -> str:
    session = get_session_factory()()
    try:
        owner = session.scalar(select(Membership).where(Membership.role == "owner"))
        assert owner is not None
        now = datetime.now(timezone.utc)
        order = Order(
            merchant_id=owner.merchant_id,
            test_order_code="DEMO-25",
            amount_minor=2500,
            currency="USD",
            status="awaiting_payer",
            created_by=owner.user_id,
            created_at=now,
        )
        payment = Payment(
            merchant_id=owner.merchant_id,
            order=order,
            idempotency_key="webhook-payment",
            paypal_order_id="ORDER-WEBHOOK",
            status="awaiting_payer",
            confirmation="confirmed",
            amount_minor=2500,
            currency="USD",
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        session.commit()
        return str(payment.id)
    finally:
        session.close()


def _status(payment_id: str) -> tuple[str, str]:
    session = get_session_factory()()
    try:
        payment = session.get(Payment, uuid.UUID(payment_id))
        assert payment is not None
        return payment.status, payment.confirmation
    finally:
        session.close()


def _event(event_id: str, status: str) -> dict[str, object]:
    return {"id": event_id, "event_type": "CHECKOUT.ORDER.COMPLETED", "resource": {"id": "ORDER-WEBHOOK", "status": status}}


def test_duplicate_event_changes_state_once(webhooks_api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.webhooks.service.verify_webhook", lambda **_kwargs: True)
    payment_id = _payment()

    first = webhooks_api.post("/api/webhooks/paypal", json=_event("WH-ONCE", "COMPLETED"))
    second = webhooks_api.post("/api/webhooks/paypal", json=_event("WH-ONCE", "FAILED"))

    assert first.status_code == 200
    assert second.status_code == 200
    assert _status(payment_id) == ("completed", "confirmed")
    session = get_session_factory()()
    try:
        events = session.scalar(select(func.count()).select_from(PayPalEvent))
        activity = session.scalar(
            select(func.count()).select_from(ActivityEvent).where(ActivityEvent.action == "payment.webhook")
        )
    finally:
        session.close()
    assert events == 1
    assert activity == 1


def test_unverified_webhook_leaves_the_payment_unchanged(webhooks_api: TestClient) -> None:
    payment_id = _payment()

    response = webhooks_api.post("/api/webhooks/paypal", json=_event("WH-BAD", "COMPLETED"))

    assert response.status_code == 200
    assert _status(payment_id) == ("awaiting_payer", "confirmed")
    session = get_session_factory()()
    try:
        events = session.scalar(select(func.count()).select_from(PayPalEvent))
    finally:
        session.close()
    assert events == 0


@pytest.fixture()
def webhooks_api():
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = get_session_factory()()
    try:
        seed_demo(session)
        session.commit()
    finally:
        session.close()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(get_engine())
