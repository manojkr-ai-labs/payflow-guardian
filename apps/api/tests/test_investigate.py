from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_paypal
from app.core.db import Base, get_engine, get_session_factory
from app.main import create_app
from app.modules.auth.models import Membership, Merchant
from app.modules.auth.seed import DEMO_ACCOUNTS, seed_demo
from app.modules.payments.models import Order, Payment
from app.modules.paypal.fake import FakePayPalAdapter
from app.modules.paypal.types import CONFIRMED, PayPalCall


def _account(role: str) -> dict[str, str]:
    return next(account for account in DEMO_ACCOUNTS if account["role"] == role)


def _login(client: TestClient, role: str = "owner") -> None:
    account = _account(role)
    response = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200


def _create_and_capture(client: TestClient, key: str) -> dict[str, object]:
    created = client.post(
        "/api/payments",
        json={"test_order_code": "DEMO-25"},
        headers={"Idempotency-Key": key},
    )
    assert created.status_code == 201
    payment_id = created.json()["payment"]["id"]
    captured = client.post(f"/api/payments/{payment_id}/capture")
    assert captured.status_code == 200
    return captured.json()["payment"]


def test_search_by_capture_id_returns_only_this_merchant(payments_api: TestClient) -> None:
    _login(payments_api)
    payment = _create_and_capture(payments_api, "search-capture")
    capture_id = payment["paypal_capture_id"]
    assert isinstance(capture_id, str)

    session = get_session_factory()()
    try:
        owner = session.scalar(select(Membership).where(Membership.role == "owner"))
        assert owner is not None
        other = Merchant(name="Other Shop")
        session.add(other)
        session.flush()
        now = datetime.now(timezone.utc)
        order = Order(
            merchant_id=other.id,
            test_order_code="DEMO-25",
            amount_minor=2500,
            currency="USD",
            status="completed",
            created_by=owner.user_id,
            created_at=now,
        )
        foreign = Payment(
            merchant_id=other.id,
            order=order,
            idempotency_key="foreign-search",
            paypal_order_id="FOREIGN-ORDER",
            paypal_capture_id="FOREIGN-CAPTURE",
            status="completed",
            confirmation=CONFIRMED,
            amount_minor=2500,
            currency="USD",
            created_at=now,
            updated_at=now,
        )
        session.add(foreign)
        session.commit()
    finally:
        session.close()

    found = payments_api.get("/api/payments", params={"q": capture_id})
    assert found.status_code == 200
    rows = found.json()["payments"]
    assert [row["id"] for row in rows] == [payment["id"]]

    hidden = payments_api.get("/api/payments", params={"q": "FOREIGN-CAPTURE"})
    assert hidden.status_code == 200
    assert hidden.json()["payments"] == []


def test_successful_read_updates_last_checked_at_and_fact_sheet(payments_api: TestClient) -> None:
    _login(payments_api)
    payment = _create_and_capture(payments_api, "investigate-ok")

    response = payments_api.post(f"/api/payments/{payment['id']}/investigate")

    assert response.status_code == 200
    body = response.json()["payment"]
    assert body["last_checked_at"]
    assert body["confirmation"] == "confirmed"
    sheet = body["fact_sheet"]
    assert sheet["paypal_status"] == "COMPLETED"
    assert sheet["local_status"] == "completed"
    assert sheet["confirmation"] == "confirmed"
    assert sheet["amount"] == "25.00"
    assert sheet["missing"] == []
    assert sheet["checked_at"] == body["last_checked_at"]


def test_failed_read_keeps_confirmed_status(payments_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(payments_api)
    payment = _create_and_capture(payments_api, "investigate-fail")

    def _boom(paypal_order_id: str | None = None, paypal_capture_id: str | None = None) -> PayPalCall:
        raise TimeoutError("timed out")

    fake_paypal.get_order_or_capture = _boom  # type: ignore[method-assign]

    response = payments_api.post(f"/api/payments/{payment['id']}/investigate")

    assert response.status_code == 200
    body = response.json()["payment"]
    assert body["status"] == "completed"
    assert body["confirmation"] == "confirmed"
    assert body["fact_sheet"]["confirmation"] == "confirmed"
    assert body["fact_sheet"]["missing"]


def test_unrecognized_paypal_status_becomes_needs_checking(
    payments_api: TestClient, fake_paypal: FakePayPalAdapter
) -> None:
    _login(payments_api)
    payment = _create_and_capture(payments_api, "investigate-unknown")
    fake_paypal.queue(
        "get_order_or_capture",
        PayPalCall(
            operation="get_order_or_capture",
            status="completed",
            confirmation=CONFIRMED,
            paypal_status="NOT_A_REAL_STATUS",
            http_status=200,
            paypal_order_id=str(payment["paypal_order_id"]),
            paypal_capture_id=str(payment["paypal_capture_id"]),
        ),
    )

    response = payments_api.post(f"/api/payments/{payment['id']}/investigate")

    assert response.status_code == 200
    body = response.json()["payment"]
    assert body["status"] == "needs_checking"
    assert body["confirmation"] == "unconfirmed"
    assert body["fact_sheet"]["paypal_status"] == "NOT_A_REAL_STATUS"
    assert body["fact_sheet"]["local_status"] == "needs_checking"


def test_amount_mismatch_needs_checking_and_keeps_the_stored_amount(
    payments_api: TestClient, fake_paypal: FakePayPalAdapter
) -> None:
    _login(payments_api)
    payment = _create_and_capture(payments_api, "investigate-mismatch")
    fake_paypal.queue(
        "get_order_or_capture",
        PayPalCall(
            operation="get_order_or_capture",
            status="completed",
            confirmation=CONFIRMED,
            paypal_status="COMPLETED",
            http_status=200,
            paypal_order_id=str(payment["paypal_order_id"]),
            paypal_capture_id=str(payment["paypal_capture_id"]),
            amount_minor=100,
            currency="USD",
        ),
    )

    response = payments_api.post(f"/api/payments/{payment['id']}/investigate")

    assert response.status_code == 200
    body = response.json()["payment"]
    assert body["status"] == "needs_checking"
    assert body["confirmation"] == "unconfirmed"
    assert body["amount_minor"] == 2500
    assert body["fact_sheet"]["mismatch"] is True
    assert body["fact_sheet"]["amount"] == "25.00"


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
