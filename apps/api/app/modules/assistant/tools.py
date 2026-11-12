from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.payments.models import Payment
from app.modules.payments.service import (
    capture_payment,
    create_test_payment,
    get_payment,
    investigate_payment,
    list_payments,
)
from app.modules.refunds.service import prepare_refund

TOOL_NAMES = frozenset(
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


@dataclass
class ToolContext:
    db: Session
    merchant_id: uuid.UUID
    user_id: uuid.UUID
    paypal: object
    web_origin: str


Tool = Callable[[dict[str, object], ToolContext], tuple[dict[str, object], Payment | None]]


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _payment_id(value: object) -> uuid.UUID | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


def _summary(payment: Payment) -> dict[str, object]:
    return {
        "payment_id": str(payment.id),
        "status": payment.status,
        "confirmation": payment.confirmation,
        "amount_minor": payment.amount_minor,
        "currency": payment.currency,
        "paypal_order_id": payment.paypal_order_id,
        "paypal_capture_id": payment.paypal_capture_id,
    }


def _not_found() -> dict[str, object]:
    return {"error": "not_found", "message": "That payment was not found."}


def _invalid(message: str) -> dict[str, object]:
    return {"error": "validation_failed", "message": message}


def find_payment(arguments: dict[str, object], ctx: ToolContext) -> tuple[dict[str, object], Payment | None]:
    query = _text(arguments.get("query")) or _text(arguments.get("payment_id"))
    if query is None:
        return _invalid("A payment id or PayPal reference is required."), None
    rows = list_payments(ctx.db, ctx.merchant_id, q=query)
    if not rows:
        return _not_found(), None
    return _summary(rows[0]), rows[0]


def list_recent_payments(arguments: dict[str, object], ctx: ToolContext) -> tuple[dict[str, object], Payment | None]:
    del arguments
    rows = list_payments(ctx.db, ctx.merchant_id)[:10]
    return {"payments": [_summary(row) for row in rows]}, None


def create_test_order(arguments: dict[str, object], ctx: ToolContext) -> tuple[dict[str, object], Payment | None]:
    code = _text(arguments.get("test_order_code"))
    if code is None:
        return _invalid("A test order code is required."), None
    key = _text(arguments.get("idempotency_key")) or str(uuid.uuid4())
    outcome = create_test_payment(
        ctx.db,
        merchant_id=ctx.merchant_id,
        user_id=ctx.user_id,
        test_order_code=code,
        idempotency_key=key,
        paypal=ctx.paypal,  # type: ignore[arg-type]
        web_origin=ctx.web_origin,
    )
    return _summary(outcome.payment), outcome.payment


def complete_approved_payment(arguments: dict[str, object], ctx: ToolContext) -> tuple[dict[str, object], Payment | None]:
    payment_id = _payment_id(arguments.get("payment_id"))
    if payment_id is None:
        return _invalid("A payment id is required."), None
    try:
        outcome = capture_payment(
            ctx.db,
            merchant_id=ctx.merchant_id,
            user_id=ctx.user_id,
            payment_id=payment_id,
            paypal=ctx.paypal,  # type: ignore[arg-type]
        )
    except AppError as exc:
        return {"error": exc.code, "message": exc.message}, None
    return _summary(outcome.payment), outcome.payment


def investigate_payment_tool(arguments: dict[str, object], ctx: ToolContext) -> tuple[dict[str, object], Payment | None]:
    payment_id = _payment_id(arguments.get("payment_id"))
    if payment_id is None:
        return _invalid("A payment id is required."), None
    try:
        payment = investigate_payment(
            ctx.db,
            merchant_id=ctx.merchant_id,
            user_id=ctx.user_id,
            payment_id=payment_id,
            paypal=ctx.paypal,  # type: ignore[arg-type]
        )
    except AppError as exc:
        return {"error": exc.code, "message": exc.message}, None
    return _summary(payment), payment


def _amount(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def prepare_refund_request(arguments: dict[str, object], ctx: ToolContext) -> tuple[dict[str, object], Payment | None]:
    payment_id = _payment_id(arguments.get("payment_id"))
    amount_minor = _amount(arguments.get("amount_minor"))
    currency = _text(arguments.get("currency"))
    reason = _text(arguments.get("reason"))
    if payment_id is None or amount_minor is None or currency is None or reason is None:
        return _invalid("A payment, amount, currency, and reason are required."), None
    try:
        outcome = prepare_refund(
            ctx.db,
            merchant_id=ctx.merchant_id,
            user_id=ctx.user_id,
            payment_id=payment_id,
            amount_minor=amount_minor,
            currency=currency,
            reason=reason,
        )
    except AppError as exc:
        return {"error": exc.code, "message": exc.message}, None
    return {
        "refund_id": str(outcome.refund.id),
        "status": outcome.refund.status,
        "payment_id": str(outcome.payment.id),
    }, outcome.payment


def check_operation_status(arguments: dict[str, object], ctx: ToolContext) -> tuple[dict[str, object], Payment | None]:
    payment_id = _payment_id(arguments.get("payment_id"))
    if payment_id is None:
        return _invalid("A payment id is required."), None
    try:
        payment = get_payment(ctx.db, ctx.merchant_id, payment_id)
    except AppError as exc:
        return {"error": exc.code, "message": exc.message}, None
    return _summary(payment), payment


TOOLS: dict[str, Tool] = {
    "find_payment": find_payment,
    "list_recent_payments": list_recent_payments,
    "create_test_order": create_test_order,
    "complete_approved_payment": complete_approved_payment,
    "investigate_payment": investigate_payment_tool,
    "prepare_refund_request": prepare_refund_request,
    "check_operation_status": check_operation_status,
}
