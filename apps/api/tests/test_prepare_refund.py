from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.deps import get_paypal
from app.core.db import Base, get_engine, get_session_factory
from app.main import create_app
from app.modules.activity.models import ActivityEvent
from app.modules.auth.models import Membership, Merchant
from app.modules.auth.seed import DEMO_ACCOUNTS, seed_demo
from app.modules.payments.models import Order, Payment
from app.modules.paypal.fake import FakePayPalAdapter
from app.modules.refunds.models import RefundRequest


def _account(role: str) -> dict[str, str]:
    return next(account for account in DEMO_ACCOUNTS if account["role"] == role)


def _login(client: TestClient, role: str = "owner") -> None:
    account = _account(role)
    response = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200


def _captured_payment(
    *,
    merchant_id,
    user_id,
    amount_minor: int = 2500,
    capture_id: str = "CAP-PREPARE-1",
    idempotency_key: str = "prepare-refund",
) -> str:
    session = get_session_factory()()
    try:
        now = datetime.now(timezone.utc)
        order = Order(
            merchant_id=merchant_id,
            test_order_code="DEMO-25",
            amount_minor=amount_minor,
            currency="USD",
            status="completed",
            created_by=user_id,
            created_at=now,
        )
        payment = Payment(
            merchant_id=merchant_id,
            order=order,
            idempotency_key=idempotency_key,
            paypal_order_id=f"ORDER-{capture_id}",
            paypal_capture_id=capture_id,
            status="completed",
            confirmation="confirmed",
            amount_minor=amount_minor,
            currency="USD",
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        session.commit()
        return str(payment.id)
    finally:
        session.close()


def _owner() -> Membership:
    session = get_session_factory()()
    try:
        owner = session.scalar(select(Membership).where(Membership.role == "owner"))
        assert owner is not None
        session.expunge(owner)
        return owner
    finally:
        session.close()


def _refund_count() -> int:
    session = get_session_factory()()
    try:
        count = session.scalar(select(func.count()).select_from(RefundRequest))
        return int(count or 0)
    finally:
        session.close()


def test_prepare_does_not_call_refund(refunds_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(refunds_api)
    owner = _owner()
    payment_id = _captured_payment(merchant_id=owner.merchant_id, user_id=owner.user_id)

    response = refunds_api.post(
        "/api/refunds",
        json={"payment_id": payment_id, "amount_minor": 2500, "currency": "USD", "reason": "Customer asked"},
    )

    assert response.status_code == 201
    body = response.json()["refund"]
    assert body["status"] == "pending_approval"
    assert body["paypal_refund_id"] is None
    assert not any(call["operation"] == "refund_capture" for call in fake_paypal.calls)
    session = get_session_factory()()
    try:
        prepared = session.scalar(select(func.count()).select_from(ActivityEvent).where(ActivityEvent.action == "refund.prepared"))
    finally:
        session.close()
    assert prepared == 1


def test_second_prepare_returns_the_same_id(refunds_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(refunds_api)
    owner = _owner()
    payment_id = _captured_payment(merchant_id=owner.merchant_id, user_id=owner.user_id, capture_id="CAP-PREPARE-2")
    payload = {"payment_id": payment_id, "amount_minor": 1000, "currency": "USD", "reason": "Duplicate check"}

    first = refunds_api.post("/api/refunds", json=payload)
    second = refunds_api.post("/api/refunds", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["refund"]["id"] == first.json()["refund"]["id"]
    assert _refund_count() == 1
    assert not any(call["operation"] == "refund_capture" for call in fake_paypal.calls)


def test_foreign_payment_is_not_found(refunds_api: TestClient) -> None:
    _login(refunds_api)
    owner = _owner()
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
            idempotency_key="foreign-prepare",
            paypal_capture_id="CAP-FOREIGN",
            status="completed",
            confirmation="confirmed",
            amount_minor=2500,
            currency="USD",
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        session.commit()
        foreign_id = str(payment.id)
    finally:
        session.close()

    response = refunds_api.post(
        "/api/refunds",
        json={"payment_id": foreign_id, "amount_minor": 100, "currency": "USD", "reason": "Not ours"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert _refund_count() == 0


def test_list_matches_the_single_refund_and_hides_foreign(refunds_api: TestClient) -> None:
    _login(refunds_api)
    owner = _owner()
    payment_id = _captured_payment(merchant_id=owner.merchant_id, user_id=owner.user_id, capture_id="CAP-LIST")
    created = refunds_api.post(
        "/api/refunds",
        json={"payment_id": payment_id, "amount_minor": 500, "currency": "USD", "reason": "List check"},
    )
    assert created.status_code == 201
    refund_id = created.json()["refund"]["id"]
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
            idempotency_key="foreign-list",
            paypal_capture_id="CAP-FOREIGN-LIST",
            status="completed",
            confirmation="confirmed",
            amount_minor=2500,
            currency="USD",
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        session.flush()
        session.add(
            RefundRequest(
                merchant_id=other.id,
                payment_id=payment.id,
                capture_id="CAP-FOREIGN-LIST",
                amount_minor=2500,
                currency="USD",
                reason="Hidden",
                payload_hash="b" * 64,
                status="pending_approval",
                prepared_by=owner.user_id,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    listed = refunds_api.get("/api/refunds")
    single = refunds_api.get(f"/api/refunds/{refund_id}")

    assert listed.status_code == 200
    rows = listed.json()["refunds"]
    assert len(rows) == 1
    assert rows[0] == single.json()["refund"]


def test_amount_above_capture_writes_nothing(refunds_api: TestClient) -> None:
    _login(refunds_api)
    owner = _owner()
    payment_id = _captured_payment(merchant_id=owner.merchant_id, user_id=owner.user_id, capture_id="CAP-PREPARE-HIGH")

    response = refunds_api.post(
        "/api/refunds",
        json={"payment_id": payment_id, "amount_minor": 2501, "currency": "USD", "reason": "Too much"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert _refund_count() == 0


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
