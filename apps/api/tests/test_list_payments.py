from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.deps import get_paypal
from app.core.db import Base, get_engine, get_session_factory
from app.main import create_app
from app.modules.auth.models import Membership, Merchant
from app.modules.auth.seed import DEMO_ACCOUNTS, seed_demo
from app.modules.payments.models import Order, Payment
from app.modules.paypal.fake import FakePayPalAdapter
from app.modules.paypal.types import CONFIRMED


def _account(role: str) -> dict[str, str]:
    return next(account for account in DEMO_ACCOUNTS if account["role"] == role)


def _login(client: TestClient, role: str) -> None:
    account = _account(role)
    response = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200


def _create_payment(client: TestClient, key: str) -> str:
    response = client.post(
        "/api/payments",
        json={"test_order_code": "DEMO-25"},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201
    return response.json()["payment"]["id"]


def test_owner_and_support_both_receive_the_created_payment(payments_api: TestClient) -> None:
    _login(payments_api, "owner")
    payment_id = _create_payment(payments_api, "list-shared")

    owner_list = payments_api.get("/api/payments")
    assert owner_list.status_code == 200
    owner_ids = [item["id"] for item in owner_list.json()["payments"]]
    assert payment_id in owner_ids
    listed = next(item for item in owner_list.json()["payments"] if item["id"] == payment_id)
    assert listed["test_order_code"] == "DEMO-25"
    assert listed["amount_minor"] == 2500
    assert listed["currency"] == "USD"
    assert "updated_at" in listed

    _login(payments_api, "support")
    support_list = payments_api.get("/api/payments")
    assert support_list.status_code == 200
    assert payment_id in [item["id"] for item in support_list.json()["payments"]]


def test_other_merchant_payment_is_hidden(payments_api: TestClient) -> None:
    _login(payments_api, "owner")
    session = get_session_factory()()
    try:
        owner = session.scalar(select(Membership).options(joinedload(Membership.user)).where(Membership.role == "owner"))
        assert owner is not None
        other = Merchant(name="Other Shop")
        session.add(other)
        session.flush()
        now = datetime.now(timezone.utc)
        order = Order(
            merchant_id=other.id,
            test_order_code="DEMO-49",
            amount_minor=4900,
            currency="USD",
            status="awaiting_payer",
            created_by=owner.user_id,
            created_at=now,
        )
        payment = Payment(
            merchant_id=other.id,
            order=order,
            idempotency_key="other-list-key",
            paypal_order_id="OTHER-LIST-1",
            status="awaiting_payer",
            confirmation=CONFIRMED,
            amount_minor=4900,
            currency="USD",
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        session.commit()
        foreign_id = str(payment.id)
    finally:
        session.close()

    listed = payments_api.get("/api/payments")
    assert listed.status_code == 200
    assert foreign_id not in [item["id"] for item in listed.json()["payments"]]

    detail = payments_api.get(f"/api/payments/{foreign_id}")
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "not_found"


def test_missing_session_cannot_list_payments(payments_api: TestClient) -> None:
    response = payments_api.get("/api/payments")
    assert response.status_code == 401


@pytest.fixture()
def fake_paypal() -> FakePayPalAdapter:
    return FakePayPalAdapter()


@pytest.fixture()
def payments_api(fake_paypal: FakePayPalAdapter):
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
