from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.assistant import get_model
from app.api.deps import get_paypal
from app.core.db import Base, get_engine, get_session_factory
from app.main import create_app
from app.modules.assistant import models as assistant_models  # noqa: F401
from app.modules.assistant.service import ModelTurn
from app.modules.assistant.tools import TOOL_NAMES, TOOLS
from app.modules.auth.models import Membership, Merchant
from app.modules.auth.seed import DEMO_ACCOUNTS, seed_demo
from app.modules.payments.models import Order, Payment
from app.modules.paypal.fake import FakePayPalAdapter
from app.modules.paypal.types import UNCONFIRMED

EXPECTED_TOOLS = frozenset(
    {
        "find_payment",
        "list_recent_payments",
        "create_test_order",
        "complete_approved_payment",
        "investigate_payment",
        "prepare_refund_request",
        "check_operation_status",
    }
)


class ModelBox:
    def __init__(self) -> None:
        self.fn = lambda _history: ModelTurn(answer="I can help with the next step.")

    def __call__(self, history: list[dict[str, object]]) -> ModelTurn:
        return self.fn(history)


def _account(role: str) -> dict[str, str]:
    return next(account for account in DEMO_ACCOUNTS if account["role"] == role)


def _login(client: TestClient, role: str) -> None:
    account = _account(role)
    response = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200


def _ask(client: TestClient, message: str = "What should I do?", conversation_id: str = "c1") -> dict[str, object]:
    response = client.post(
        "/api/assistant/messages",
        json={"message": message, "conversation_id": conversation_id},
    )
    assert response.status_code == 200
    return response.json()


def test_tool_names_are_the_allowlist() -> None:
    assert TOOL_NAMES == EXPECTED_TOOLS
    assert set(TOOLS) == EXPECTED_TOOLS
    assert TOOL_NAMES.isdisjoint({"approve", "reject", "send", "approve_refund", "send_refund"})


def test_unknown_tool_is_rejected(assistant_api: TestClient, model_box: ModelBox) -> None:
    _login(assistant_api, "owner")
    seen: dict[str, object] = {}

    def model(history: list[dict[str, object]]) -> ModelTurn:
        tools = [item for item in history if item.get("role") == "tool"]
        if not tools:
            return ModelTurn(tool_name="approve_refund", arguments={})
        seen["result"] = tools[-1]["content"]
        return ModelTurn(answer="That tool is not available.")

    model_box.fn = model
    body = _ask(assistant_api, conversation_id="unknown-tool")
    assert seen["result"] == {"error": "unknown_tool", "message": "That tool is not available."}
    assert body["answer"] == "That tool is not available."


def test_unconfirmed_fact_sheet_stays_unconfirmed(assistant_api: TestClient, model_box: ModelBox) -> None:
    _login(assistant_api, "owner")
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
            status="needs_checking",
            created_by=owner.user_id,
            created_at=now,
        )
        payment = Payment(
            merchant_id=owner.merchant_id,
            order=order,
            idempotency_key="unconfirmed-assistant",
            status="needs_checking",
            confirmation=UNCONFIRMED,
            amount_minor=2500,
            currency="USD",
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        session.commit()
        payment_id = str(payment.id)
    finally:
        session.close()

    def model(history: list[dict[str, object]]) -> ModelTurn:
        if not any(item.get("role") == "tool" for item in history):
            return ModelTurn(tool_name="check_operation_status", arguments={"payment_id": payment_id})
        return ModelTurn(answer="The payment is completed.")

    model_box.fn = model
    body = _ask(assistant_api, conversation_id="unconfirmed")
    assert body["confirmation"] == "unconfirmed"
    assert body["fact_sheet"]["confirmation"] == "unconfirmed"
    assert body["next_step"] == "refresh_payment"


def test_create_test_order_uses_catalog_amount(assistant_api: TestClient, model_box: ModelBox) -> None:
    _login(assistant_api, "owner")

    def model(history: list[dict[str, object]]) -> ModelTurn:
        if not any(item.get("role") == "tool" for item in history):
            return ModelTurn(
                tool_name="create_test_order",
                arguments={
                    "test_order_code": "DEMO-25",
                    "amount_minor": 1,
                    "currency": "EUR",
                    "idempotency_key": "assistant-demo-25",
                },
            )
        return ModelTurn(answer="Created the catalog order.")

    model_box.fn = model
    _ask(assistant_api, conversation_id="create-order")
    session = get_session_factory()()
    try:
        payment = session.scalar(select(Payment).where(Payment.idempotency_key == "assistant-demo-25"))
        assert payment is not None
        assert payment.amount_minor == 2500
        assert payment.currency == "USD"
    finally:
        session.close()


def test_foreign_payment_is_not_found(assistant_api: TestClient, model_box: ModelBox) -> None:
    _login(assistant_api, "owner")
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
        payment = Payment(
            merchant_id=other.id,
            order=order,
            idempotency_key="foreign-assistant",
            paypal_order_id="FOREIGN-ASSISTANT",
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

    seen: dict[str, object] = {}

    def model(history: list[dict[str, object]]) -> ModelTurn:
        tools = [item for item in history if item.get("role") == "tool"]
        if not tools:
            return ModelTurn(tool_name="find_payment", arguments={"payment_id": foreign_id})
        seen["result"] = tools[-1]["content"]
        return ModelTurn(answer="That payment was not found.")

    model_box.fn = model
    body = _ask(assistant_api, conversation_id="foreign")
    assert seen["result"]["error"] == "not_found"
    assert body["answer"] == "That payment was not found."


def test_owner_and_support_can_call_the_assistant(assistant_api: TestClient) -> None:
    _login(assistant_api, "owner")
    owner_body = _ask(assistant_api, conversation_id="owner-chat")
    assert isinstance(owner_body["answer"], str)
    _login(assistant_api, "support")
    support_body = _ask(assistant_api, conversation_id="support-chat")
    assert isinstance(support_body["answer"], str)


def test_prepare_refund_does_not_write_a_payment(assistant_api: TestClient, model_box: ModelBox) -> None:
    _login(assistant_api, "owner")
    session = get_session_factory()()
    try:
        before = session.scalar(select(func.count()).select_from(Payment))
    finally:
        session.close()

    def model(history: list[dict[str, object]]) -> ModelTurn:
        if not any(item.get("role") == "tool" for item in history):
            return ModelTurn(tool_name="prepare_refund_request", arguments={"payment_id": "pay_123", "amount_minor": 100})
        return ModelTurn(answer="Not yet.")

    model_box.fn = model
    body = _ask(assistant_api, conversation_id="prepare")
    assert "available in the next phase" in str(body["answer"]) or body["answer"] == "Not yet."
    session = get_session_factory()()
    try:
        after = session.scalar(select(func.count()).select_from(Payment))
    finally:
        session.close()
    assert after == before


@pytest.fixture()
def fake_paypal() -> FakePayPalAdapter:
    return FakePayPalAdapter()


@pytest.fixture()
def model_box() -> ModelBox:
    return ModelBox()


@pytest.fixture()
def assistant_api(fake_paypal: FakePayPalAdapter, model_box: ModelBox):
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
    app.dependency_overrides[get_model] = lambda: model_box
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(get_engine())
