import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_paypal
from app.core.db import Base, get_engine, get_session_factory
from app.core.errors import AppError
from app.main import create_app
from app.modules.activity.models import ActivityEvent
from app.modules.auth.models import Membership, Merchant, User
from app.modules.auth.seed import DEMO_ACCOUNTS, seed_demo
from app.modules.payments.models import Order, Payment
from app.modules.payments.sandbox_check import create_demo_order, main
from app.modules.payments import service
from app.modules.payments.service import create_test_payment
from app.modules.paypal.fake import FakePayPalAdapter
from app.modules.paypal.sandbox_check import credentials_present
from app.modules.paypal.types import CONFIRMED, NEEDS_CHECKING, PAYPAL_FAILED, UNCONFIRMED, PayPalCall

WEB_ORIGIN = "http://localhost:3000"


def _membership(db: Session, role: str = "owner") -> Membership:
    membership = db.scalar(
        select(Membership).options(joinedload(Membership.user), joinedload(Membership.merchant)).where(Membership.role == role)
    )
    assert membership is not None
    return membership


def _create(db: Session, fake: FakePayPalAdapter, *, code: str = "DEMO-25", key: str = "key-1", role: str = "owner"):
    membership = _membership(db, role)
    return create_test_payment(
        db,
        merchant_id=membership.merchant_id,
        user_id=membership.user_id,
        test_order_code=code,
        idempotency_key=key,
        paypal=fake,
        web_origin=WEB_ORIGIN,
    )


def _account(role: str) -> dict[str, str]:
    return next(account for account in DEMO_ACCOUNTS if account["role"] == role)


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


def _login(client: TestClient, role: str = "owner") -> None:
    account = _account(role)
    response = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200


def test_demo_25_persists_catalog_amount_when_client_sends_another_amount(payments_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(payments_api)
    response = payments_api.post(
        "/api/payments",
        json={"test_order_code": "demo-25", "amount": 1, "amount_minor": 1, "currency": "EUR"},
        headers={"Idempotency-Key": "amount-key"},
    )
    assert response.status_code == 201
    body = response.json()["payment"]
    assert body["test_order_code"] == "DEMO-25"
    assert body["amount_minor"] == 2500
    assert body["display_amount"] == "25.00"
    assert body["currency"] == "USD"
    assert body["status"] == "awaiting_payer"
    assert body["confirmation"] == "confirmed"
    assert body["paypal_order_id"]
    assert body["approve_url"].startswith("https://")
    assert "amount" not in response.json()
    assert fake_paypal.calls == [
        {
            "operation": "create_order",
            "amount_minor": 2500,
            "currency": "USD",
            "return_url": f"{WEB_ORIGIN}/payments/{body['id']}/return",
            "cancel_url": f"{WEB_ORIGIN}/payments/{body['id']}/cancel",
        }
    ]

    session = get_session_factory()()
    try:
        stored = session.scalar(select(Payment).options(joinedload(Payment.order)))
        assert stored is not None
        assert stored.amount_minor == 2500
        assert stored.currency == "USD"
        assert stored.order.amount_minor == 2500
        assert stored.order.currency == "USD"
        assert stored.order.test_order_code == "DEMO-25"
        event = session.scalar(select(ActivityEvent).where(ActivityEvent.action == "payment.created"))
        assert event is not None
        assert event.amount_minor == 2500
        assert event.currency == "USD"
        assert event.outcome == "confirmed"
        assert event.paypal_reference == stored.paypal_order_id
        assert "approve" not in (event.summary or "")
    finally:
        session.close()


def test_demo_49_uses_catalog_amount(db: Session) -> None:
    outcome = _create(db, FakePayPalAdapter(), code="DEMO-49", key="demo-49")
    assert outcome.error is None
    assert outcome.payment.amount_minor == 4900
    assert outcome.payment.currency == "USD"
    assert outcome.payment.order.amount_minor == 4900


def test_repeated_idempotency_key_creates_one_paypal_order(db: Session) -> None:
    fake = FakePayPalAdapter()
    first = _create(db, fake, key="same-key")
    second = _create(db, fake, key="same-key")
    assert first.inserted is True
    assert second.inserted is False
    assert second.payment.id == first.payment.id
    assert second.error is None
    assert len(fake.calls) == 1
    events = db.scalars(select(ActivityEvent).where(ActivityEvent.action == "payment.created")).all()
    assert len(events) == 1


def test_unknown_code_creates_no_row(db: Session) -> None:
    fake = FakePayPalAdapter()
    with pytest.raises(AppError) as caught:
        _create(db, fake, code="NO-SUCH")
    assert caught.value.code == "validation_failed"
    assert db.scalar(select(func.count()).select_from(Order)) == 0
    assert db.scalar(select(func.count()).select_from(Payment)) == 0
    assert fake.calls == []


def test_missing_idempotency_key_creates_no_row(payments_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(payments_api)
    response = payments_api.post("/api/payments", json={"test_order_code": "DEMO-25"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert "payment" not in response.json()
    assert fake_paypal.calls == []
    session = get_session_factory()()
    try:
        assert session.scalar(select(func.count()).select_from(Payment)) == 0
    finally:
        session.close()


def test_same_key_with_a_different_code_is_rejected(db: Session) -> None:
    fake = FakePayPalAdapter()
    first = _create(db, fake, code="DEMO-25", key="shared")
    with pytest.raises(AppError) as caught:
        _create(db, fake, code="DEMO-49", key="shared")
    assert caught.value.code == "validation_failed"
    assert first.payment.amount_minor == 2500
    assert first.payment.order.test_order_code == "DEMO-25"
    assert len(fake.calls) == 1
    assert db.scalar(select(func.count()).select_from(Payment)) == 1


def test_idempotency_key_is_scoped_to_the_merchant(db: Session) -> None:
    fake = FakePayPalAdapter()
    owner = _membership(db)
    other_merchant = Merchant(name="Other Shop")
    other_user = User(email="other@payflow.test", display_name="Other Owner", password_hash="not-used")
    db.add(other_merchant)
    db.add(other_user)
    db.flush()
    first = _create(db, fake, key="shared-key")
    second = create_test_payment(
        db,
        merchant_id=other_merchant.id,
        user_id=other_user.id,
        test_order_code="DEMO-25",
        idempotency_key="shared-key",
        paypal=fake,
        web_origin=WEB_ORIGIN,
    )
    assert first.payment.id != second.payment.id
    assert first.payment.merchant_id == owner.merchant_id
    assert second.payment.merchant_id == other_merchant.id
    assert len(fake.calls) == 2


def test_explicit_paypal_failure_stores_failed_and_returns_paypal_failed(db: Session) -> None:
    fake = FakePayPalAdapter()
    fake.queue(
        "create_order",
        PayPalCall(
            operation="create_order",
            status="failed",
            confirmation=UNCONFIRMED,
            error_code=PAYPAL_FAILED,
            message="PayPal rejected the order.",
            http_status=422,
        ),
    )
    outcome = _create(db, fake)
    assert outcome.inserted is True
    assert outcome.error is not None
    assert outcome.error.code == "paypal_failed"
    assert outcome.error.message == "PayPal rejected the order."
    assert outcome.payment.status == "failed"
    assert outcome.payment.confirmation == "unconfirmed"
    assert outcome.payment.paypal_order_id is None
    assert outcome.payment.amount_minor == 2500
    event = db.scalar(select(ActivityEvent).where(ActivityEvent.action == "payment.created"))
    assert event is not None
    assert event.outcome == "failed"


def test_timeout_stores_needs_checking_and_replay_does_not_call_paypal_again(db: Session) -> None:
    fake = FakePayPalAdapter()
    fake.queue(
        "create_order",
        PayPalCall(
            operation="create_order",
            status=NEEDS_CHECKING,
            confirmation=UNCONFIRMED,
            error_code=NEEDS_CHECKING,
            message="PayPal did not answer. The payment needs a check.",
        ),
    )
    first = _create(db, fake, key="timeout-key")
    second = _create(db, fake, key="timeout-key")
    assert first.error is not None
    assert first.error.code == "needs_checking"
    assert first.payment.status == "needs_checking"
    assert first.payment.confirmation == "unconfirmed"
    assert first.payment.paypal_order_id is None
    assert second.payment.id == first.payment.id
    assert second.inserted is False
    assert len(fake.calls) == 1


def test_unrecognized_status_stores_the_paypal_order_id(db: Session) -> None:
    fake = FakePayPalAdapter()
    fake.queue(
        "create_order",
        PayPalCall(
            operation="create_order",
            status=NEEDS_CHECKING,
            confirmation=UNCONFIRMED,
            error_code=NEEDS_CHECKING,
            paypal_status="FROBNICATED",
            paypal_order_id="ORDER-UNKNOWN",
            approve_url="https://example.test/approve/ORDER-UNKNOWN",
            amount_minor=2500,
            currency="USD",
        ),
    )
    outcome = _create(db, fake)
    assert outcome.error is not None
    assert outcome.error.code == "needs_checking"
    assert outcome.payment.status == "needs_checking"
    assert outcome.payment.confirmation == "unconfirmed"
    assert outcome.payment.paypal_order_id == "ORDER-UNKNOWN"
    assert outcome.payment.approve_url is None
    assert outcome.payment.amount_minor == 2500


def test_paypal_amount_mismatch_keeps_the_catalog_amount(db: Session) -> None:
    fake = FakePayPalAdapter()
    fake.queue(
        "create_order",
        PayPalCall(
            operation="create_order",
            status="awaiting_payer",
            confirmation=CONFIRMED,
            paypal_status="PAYER_ACTION_REQUIRED",
            paypal_order_id="ORDER-MISMATCH",
            approve_url="https://example.test/approve/ORDER-MISMATCH",
            amount_minor=100,
            currency="EUR",
        ),
    )
    outcome = _create(db, fake)
    assert outcome.error is not None
    assert outcome.error.code == "needs_checking"
    assert outcome.payment.amount_minor == 2500
    assert outcome.payment.currency == "USD"
    assert outcome.payment.paypal_order_id == "ORDER-MISMATCH"
    assert outcome.payment.status == "needs_checking"
    assert fake.calls[0]["amount_minor"] == 2500
    assert fake.calls[0]["currency"] == "USD"


def test_create_and_activity_roll_back_together(db: Session) -> None:
    outcome = _create(db, FakePayPalAdapter(), key="rollback-key")
    payment_id = outcome.payment.id
    db.rollback()
    assert db.get(Payment, payment_id) is None
    assert db.scalar(select(ActivityEvent).where(ActivityEvent.entity_id == payment_id)) is None


def test_catalog_lists_server_orders_for_a_signed_in_merchant(payments_api: TestClient) -> None:
    denied = payments_api.get("/api/catalog/test-orders")
    assert denied.status_code == 401
    _login(payments_api, "support")
    response = payments_api.get("/api/catalog/test-orders")
    assert response.status_code == 200
    assert response.json()["test_orders"] == [
        {
            "code": "DEMO-25",
            "description": "Demo consultation",
            "amount_minor": 2500,
            "display_amount": "25.00",
            "currency": "USD",
        },
        {
            "code": "DEMO-49",
            "description": "Demo product",
            "amount_minor": 4900,
            "display_amount": "49.00",
            "currency": "USD",
        },
    ]


def test_support_can_create_a_test_order(payments_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(payments_api, "support")
    response = payments_api.post(
        "/api/payments",
        json={"test_order_code": "DEMO-25"},
        headers={"Idempotency-Key": "support-key"},
    )
    assert response.status_code == 201
    assert response.json()["payment"]["amount_minor"] == 2500
    assert len(fake_paypal.calls) == 1


def test_replay_after_success_returns_the_same_payment(payments_api: TestClient, fake_paypal: FakePayPalAdapter) -> None:
    _login(payments_api)
    headers = {"Idempotency-Key": "http-replay"}
    first = payments_api.post("/api/payments", json={"test_order_code": "DEMO-25"}, headers=headers)
    second = payments_api.post("/api/payments", json={"test_order_code": "DEMO-25"}, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["payment"]["id"] == first.json()["payment"]["id"]
    assert len(fake_paypal.calls) == 1


def test_unique_key_conflict_returns_the_original_payment(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakePayPalAdapter()
    first = _create(db, fake, key="race-key")
    real_find = service._find
    state = {"calls": 0}

    def miss_once(session: Session, merchant_id, key: str):
        state["calls"] += 1
        if state["calls"] == 1:
            return None
        return real_find(session, merchant_id, key)

    monkeypatch.setattr(service, "_find", miss_once)
    second = _create(db, fake, key="race-key")
    assert second.inserted is False
    assert second.payment.id == first.payment.id
    assert len(fake.calls) == 1
    assert db.scalar(select(func.count()).select_from(Payment)) == 1


def test_sandbox_order_check_skips_without_credentials(capsys: pytest.CaptureFixture[str]) -> None:
    assert credentials_present() is False
    assert create_demo_order() is None
    assert main() == 0
    assert capsys.readouterr().out.strip() == "skipped"


@pytest.mark.skipif(not credentials_present(), reason="PayPal Sandbox credentials are absent")
def test_sandbox_approval_link_uses_the_catalog_amount() -> None:
    result = create_demo_order()
    assert result is not None
    assert result.http_status == 201
    assert result.paypal_order_id
    assert result.approve_url
    assert result.amount_minor == 2500
    assert result.currency == "USD"
    assert result.error_code is None
