import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.deps import get_paypal
from app.core.db import Base, get_engine, get_session_factory
from app.main import create_app
from app.modules.auth.models import Membership, Merchant
from app.modules.auth.seed import DEMO_ACCOUNTS, seed_demo
from app.modules.payments.models import Order, Payment
from app.modules.paypal.fake import FakePayPalAdapter
from app.modules.paypal.types import NEEDS_CHECKING, UNCONFIRMED, PayPalCall
from app.modules.refunds.models import RefundRequest


def _account(role: str) -> dict[str, str]:
    return next(account for account in DEMO_ACCOUNTS if account["role"] == role)


def _login(client: TestClient, role: str = "owner") -> None:
    account = _account(role)
    response = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200


def _membership(role: str) -> Membership:
    session = get_session_factory()()
    try:
        membership = session.scalar(select(Membership).where(Membership.role == role))
        assert membership is not None
        session.expunge(membership)
        return membership
    finally:
        session.close()


def _captured_payment(*, merchant_id, user_id, capture_id: str) -> str:
    session = get_session_factory()()
    try:
        now = datetime.now(timezone.utc)
        order = Order(
            merchant_id=merchant_id,
            test_order_code="DEMO-25",
            amount_minor=2500,
            currency="USD",
            status="completed",
            created_by=user_id,
            created_at=now,
        )
        payment = Payment(
            merchant_id=merchant_id,
            order=order,
            idempotency_key=capture_id,
            paypal_order_id=f"ORDER-{capture_id}",
            paypal_capture_id=capture_id,
            status="completed",
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


def _prepare(client: TestClient, payment_id: str) -> dict[str, object]:
    response = client.post(
        "/api/refunds",
        json={"payment_id": payment_id, "amount_minor": 2500, "currency": "USD", "reason": "Customer asked"},
    )
    assert response.status_code == 201
    return response.json()["refund"]


def _refund_calls(fake: FakePayPalAdapter) -> list[dict[str, object]]:
    return [call for call in fake.calls if call["operation"] == "refund_capture"]


def _refund_count() -> int:
    session = get_session_factory()()
    try:
        count = session.scalar(select(func.count()).select_from(RefundRequest))
        return int(count or 0)
    finally:
        session.close()


def test_owner_approve_calls_refund_once(refunds_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(refunds_api)
    owner = _membership("owner")
    payment_id = _captured_payment(merchant_id=owner.merchant_id, user_id=owner.user_id, capture_id="CAP-APPROVE")
    refund_id = _prepare(refunds_api, payment_id)["id"]

    first = refunds_api.post(f"/api/refunds/{refund_id}/approve")
    second = refunds_api.post(f"/api/refunds/{refund_id}/approve")

    assert first.status_code == 200
    body = first.json()["refund"]
    assert body["status"] == "completed"
    assert body["paypal_refund_id"]
    assert second.status_code == 200
    assert second.json()["refund"]["id"] == refund_id
    assert second.json()["refund"]["paypal_refund_id"] == body["paypal_refund_id"]
    assert len(_refund_calls(fake_paypal)) == 1
    assert _refund_count() == 1


def test_hash_mismatch_does_not_call_paypal(refunds_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(refunds_api)
    owner = _membership("owner")
    payment_id = _captured_payment(merchant_id=owner.merchant_id, user_id=owner.user_id, capture_id="CAP-STALE")
    refund_id = _prepare(refunds_api, payment_id)["id"]
    session = get_session_factory()()
    try:
        refund = session.get(RefundRequest, uuid.UUID(str(refund_id)))
        assert refund is not None
        refund.payload_hash = "0" * 64
        session.commit()
    finally:
        session.close()

    response = refunds_api.post(f"/api/refunds/{refund_id}/approve")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "approval_stale"
    assert _refund_calls(fake_paypal) == []
    session = get_session_factory()()
    try:
        refund = session.get(RefundRequest, uuid.UUID(str(refund_id)))
        assert refund is not None
        assert refund.status == "pending_approval"
        assert refund.approved_by is None
    finally:
        session.close()


def test_support_approve_is_forbidden(refunds_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(refunds_api, "support")
    support = _membership("support")
    payment_id = _captured_payment(merchant_id=support.merchant_id, user_id=support.user_id, capture_id="CAP-SUPPORT")
    refund_id = _prepare(refunds_api, payment_id)["id"]

    response = refunds_api.post(f"/api/refunds/{refund_id}/approve")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert _refund_calls(fake_paypal) == []


def test_unclear_refund_needs_checking_and_is_not_sent_again(
    refunds_api: TestClient, fake_paypal: FakePayPalAdapter
) -> None:
    _login(refunds_api)
    owner = _membership("owner")
    payment_id = _captured_payment(merchant_id=owner.merchant_id, user_id=owner.user_id, capture_id="CAP-UNCLEAR")
    refund_id = _prepare(refunds_api, payment_id)["id"]
    fake_paypal.queue(
        "refund_capture",
        PayPalCall(
            operation="refund_capture",
            status=NEEDS_CHECKING,
            confirmation=UNCONFIRMED,
            error_code=NEEDS_CHECKING,
            message="PayPal did not answer.",
        ),
    )

    first = refunds_api.post(f"/api/refunds/{refund_id}/approve")
    second = refunds_api.post(f"/api/refunds/{refund_id}/approve")

    assert first.status_code == 409
    assert first.json()["error"]["code"] == "needs_checking"
    assert first.json()["refund"]["status"] == "needs_checking"
    assert first.json()["refund"]["id"] == refund_id
    assert second.json()["refund"]["id"] == refund_id
    assert second.json()["refund"]["status"] == "needs_checking"
    assert len(_refund_calls(fake_paypal)) == 1
    assert _refund_count() == 1


def test_foreign_refund_is_not_found(refunds_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(refunds_api)
    owner = _membership("owner")
    session = get_session_factory()()
    try:
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
        payment = Payment(
            merchant_id=other.id,
            order=order,
            idempotency_key="foreign-approve",
            paypal_capture_id="CAP-FOREIGN-APPROVE",
            status="completed",
            confirmation="confirmed",
            amount_minor=2500,
            currency="USD",
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        session.flush()
        refund = RefundRequest(
            merchant_id=other.id,
            payment_id=payment.id,
            capture_id="CAP-FOREIGN-APPROVE",
            amount_minor=2500,
            currency="USD",
            reason="Other shop",
            payload_hash="a" * 64,
            status="pending_approval",
            prepared_by=owner.user_id,
            created_at=now,
            updated_at=now,
        )
        session.add(refund)
        session.commit()
        foreign_id = str(refund.id)
    finally:
        session.close()

    response = refunds_api.post(f"/api/refunds/{foreign_id}/approve")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert _refund_calls(fake_paypal) == []


def test_reject_does_not_call_paypal(refunds_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(refunds_api)
    owner = _membership("owner")
    payment_id = _captured_payment(merchant_id=owner.merchant_id, user_id=owner.user_id, capture_id="CAP-REJECT")
    refund_id = _prepare(refunds_api, payment_id)["id"]

    response = refunds_api.post(f"/api/refunds/{refund_id}/reject")

    assert response.status_code == 200
    assert response.json()["refund"]["status"] == "rejected"
    assert _refund_calls(fake_paypal) == []


@pytest.fixture()
def fake_paypal() -> FakePayPalAdapter:
    return FakePayPalAdapter()


@pytest.fixture()
def refunds_api(fake_paypal: FakePayPalAdapter):
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
