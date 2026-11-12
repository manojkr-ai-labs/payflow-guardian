import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_paypal
from app.core.db import Base, get_engine, get_session_factory
from app.main import create_app
from app.modules.auth.models import Membership, Merchant
from app.modules.auth.seed import DEMO_ACCOUNTS, seed_demo
from app.modules.payments.models import Order, Payment
from app.modules.paypal.fake import FakePayPalAdapter
from app.modules.paypal.types import CONFIRMED, NEEDS_CHECKING, UNCONFIRMED, PayPalCall


def _account(role: str) -> dict[str, str]:
    return next(account for account in DEMO_ACCOUNTS if account["role"] == role)


def _login(client: TestClient, role: str = "owner") -> None:
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


def _capture_calls(fake: FakePayPalAdapter) -> list[dict[str, object]]:
    return [call for call in fake.calls if call["operation"] == "capture_order"]


def test_successful_capture_stores_capture_id_and_confirmed(payments_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(payments_api)
    payment_id = _create_payment(payments_api, "capture-success")

    response = payments_api.post(f"/api/payments/{payment_id}/capture")

    assert response.status_code == 200
    body = response.json()["payment"]
    assert body["status"] == "completed"
    assert body["confirmation"] == "confirmed"
    assert body["paypal_capture_id"]
    sheet = body["fact_sheet"]
    assert sheet["paypal_capture_id"] == body["paypal_capture_id"]
    assert sheet["paypal_status"] == "COMPLETED"
    assert sheet["local_status"] == "completed"
    assert sheet["confirmation"] == "confirmed"
    assert len(_capture_calls(fake_paypal)) == 1


def test_second_capture_does_not_call_paypal_again(payments_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(payments_api)
    payment_id = _create_payment(payments_api, "capture-twice")

    first = payments_api.post(f"/api/payments/{payment_id}/capture")
    second = payments_api.post(f"/api/payments/{payment_id}/capture")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["payment"]["paypal_capture_id"] == first.json()["payment"]["paypal_capture_id"]
    assert len(_capture_calls(fake_paypal)) == 1


def test_unclear_capture_stores_needs_checking_after_one_attempt(
    payments_api: TestClient, fake_paypal: FakePayPalAdapter
) -> None:
    _login(payments_api)
    payment_id = _create_payment(payments_api, "capture-unclear")
    fake_paypal.queue(
        "capture_order",
        PayPalCall(
            operation="capture_order",
            status=NEEDS_CHECKING,
            confirmation=UNCONFIRMED,
            error_code=NEEDS_CHECKING,
            message="PayPal did not answer.",
        ),
    )

    response = payments_api.post(f"/api/payments/{payment_id}/capture")

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "needs_checking"
    assert body["payment"]["status"] == "needs_checking"
    assert body["payment"]["confirmation"] == "unconfirmed"
    assert len(_capture_calls(fake_paypal)) == 1


def test_capture_timeout_stores_needs_checking_after_one_attempt(
    payments_api: TestClient, fake_paypal: FakePayPalAdapter
) -> None:
    _login(payments_api)
    payment_id = _create_payment(payments_api, "capture-timeout")

    def _boom(paypal_order_id: str) -> PayPalCall:
        fake_paypal.calls.append({"operation": "capture_order", "paypal_order_id": paypal_order_id})
        raise TimeoutError("timed out")

    fake_paypal.capture_order = _boom  # type: ignore[method-assign]

    response = payments_api.post(f"/api/payments/{payment_id}/capture")

    assert response.status_code == 409
    assert response.json()["payment"]["status"] == "needs_checking"
    assert len(_capture_calls(fake_paypal)) == 1


def test_unknown_payment_returns_not_found(payments_api: TestClient) -> None:
    _login(payments_api)

    response = payments_api.post(f"/api/payments/{uuid.uuid4()}/capture")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_other_merchant_payment_returns_not_found(payments_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(payments_api)
    session = get_session_factory()()
    try:
        owner = session.scalar(
            select(Membership).options(joinedload(Membership.user)).where(Membership.role == "owner")
        )
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
            status="awaiting_payer",
            created_by=owner.user_id,
            created_at=now,
        )
        payment = Payment(
            merchant_id=other.id,
            order=order,
            idempotency_key="other-merchant-key",
            paypal_order_id="OTHER-ORDER-1",
            status="awaiting_payer",
            confirmation=CONFIRMED,
            amount_minor=2500,
            currency="USD",
            approve_url="https://example.test/paypal/approve/OTHER-ORDER-1",
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        session.commit()
        foreign_id = payment.id
    finally:
        session.close()

    response = payments_api.post(f"/api/payments/{foreign_id}/capture")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert _capture_calls(fake_paypal) == []


import pytest


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
