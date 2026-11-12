from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.assistant.model import Model, ModelTurn, default_model
from app.modules.assistant.models import AssistantMessage
from app.modules.assistant.tools import TOOLS, ToolContext
from app.modules.payments.models import Payment

MAX_TOOL_CALLS = 3


def _next_step(payment: Payment | None) -> str | None:
    if payment is None:
        return None
    if payment.status == "failed":
        return "show_failure"
    if payment.status == "completed" and payment.confirmation == "confirmed":
        return "prepare_refund"
    if payment.status == "awaiting_payer":
        return "approve_on_paypal"
    if payment.status == "needs_checking" or payment.confirmation != "confirmed":
        return "refresh_payment"
    return None


def _amount(amount_minor: int) -> str:
    whole, cents = divmod(amount_minor, 100)
    return f"{whole}.{cents:02d}"


def _fact_sheet(payment: Payment) -> dict[str, object]:
    stored: dict[str, object] = {}
    if payment.fact_sheet:
        try:
            parsed = json.loads(payment.fact_sheet)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            stored = parsed
    stored["payment_id"] = str(payment.id)
    stored["confirmation"] = payment.confirmation
    stored["local_status"] = payment.status
    stored.setdefault("paypal_order_id", payment.paypal_order_id)
    stored.setdefault("paypal_capture_id", payment.paypal_capture_id)
    stored.setdefault("paypal_status", payment.paypal_status)
    stored.setdefault("amount", _amount(payment.amount_minor))
    stored.setdefault("currency", payment.currency)
    stored.setdefault("missing", [])
    return stored


def _save(
    db: Session,
    *,
    merchant_id: uuid.UUID,
    user_id: uuid.UUID,
    conversation_id: str,
    role: str,
    content: str,
    tool_name: str | None = None,
) -> None:
    db.add(
        AssistantMessage(
            merchant_id=merchant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_name=tool_name,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.flush()


def handle_message(
    db: Session,
    *,
    merchant_id: uuid.UUID,
    user_id: uuid.UUID,
    message: str,
    conversation_id: str,
    paypal: object,
    web_origin: str,
    model: Model | None = None,
) -> dict[str, object]:
    chosen = model or default_model
    _save(
        db,
        merchant_id=merchant_id,
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=message,
    )
    history: list[dict[str, object]] = [{"role": "user", "content": message}]
    focused: Payment | None = None
    answer = "I could not finish the explanation."
    context = ToolContext(
        db=db,
        merchant_id=merchant_id,
        user_id=user_id,
        paypal=paypal,
        web_origin=web_origin,
    )
    for _ in range(MAX_TOOL_CALLS):
        turn = chosen(history)
        if not turn.tool_name:
            if turn.answer:
                answer = turn.answer
            break
        arguments = turn.arguments or {}
        if turn.tool_name not in TOOLS:
            result: dict[str, object] = {"error": "unknown_tool", "message": "That tool is not available."}
            payment = None
        else:
            result, payment = TOOLS[turn.tool_name](arguments, context)
        if payment is not None:
            focused = payment
        history.append({"role": "tool", "tool_name": turn.tool_name, "content": result})
        _save(
            db,
            merchant_id=merchant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            role="tool",
            content=json.dumps(result),
            tool_name=turn.tool_name,
        )
    else:
        turn = chosen(history)
        if turn.answer and not turn.tool_name:
            answer = turn.answer
    _save(
        db,
        merchant_id=merchant_id,
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
    )
    return {
        "answer": answer,
        "next_step": _next_step(focused),
        "confirmation": focused.confirmation if focused else None,
        "fact_sheet": _fact_sheet(focused) if focused else None,
    }
