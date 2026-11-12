from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_paypal
from app.core.db import Base, get_engine, get_session_factory
from app.main import create_app
from app.modules.activity.models import ActivityEvent
from app.modules.auth.models import Membership, Merchant
from app.modules.auth.seed import DEMO_ACCOUNTS, seed_demo
from app.modules.paypal.fake import FakePayPalAdapter

FORBIDDEN_FIELDS = {"authorization", "client_secret", "api_key", "password", "access_token"}


def _login(client: TestClient) -> None:
    account = next(account for account in DEMO_ACCOUNTS if account["role"] == "owner")
    response = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200


def test_activity_feed_is_merchant_scoped_and_has_no_secrets(activity_api: TestClient) -> None:
    _login(activity_api)
    created = activity_api.post(
        "/api/payments",
        json={"test_order_code": "DEMO-25"},
        headers={"Idempotency-Key": "activity-feed-demo-25"},
    )
    assert created.status_code == 201

    session = get_session_factory()()
    try:
        owner = session.scalar(select(Membership).where(Membership.role == "owner"))
        assert owner is not None
        other = Merchant(name="Other Shop")
        session.add(other)
        session.flush()
        session.add(
            ActivityEvent(
                merchant_id=other.id,
                actor_type="system",
                action="payment.created",
                entity_type="payment",
                summary="Foreign activity must stay hidden.",
                outcome="confirmed",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    finally:
        session.close()

    response = activity_api.get("/api/activity")
    assert response.status_code == 200
    events = response.json()["events"]
    assert any(event["action"] == "payment.created" for event in events)
    assert all("Foreign activity must stay hidden." not in event["summary"] for event in events)
    assert all(FORBIDDEN_FIELDS.isdisjoint(event) for event in events)


@pytest.fixture()
def fake_paypal() -> FakePayPalAdapter:
    return FakePayPalAdapter()


@pytest.fixture()
def activity_api(fake_paypal: FakePayPalAdapter):
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
    app.dependency_overrides[get_paypal] = lambda: fake_paypal
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(get_engine())
