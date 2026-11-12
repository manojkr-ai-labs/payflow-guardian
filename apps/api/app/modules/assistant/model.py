"""Assistant model. The built-in planner investigates without a network.

A configured chat API is used only when the base URL, key, and model name are
all set. The API key stays in the request header and is not written to the
answer, the database, or the log line.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Callable

import httpx

from app.core.config import Settings

logger = logging.getLogger("app.assistant")

UNAVAILABLE = "The explanation could not be completed."

_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_CODE = re.compile(r"\bDEMO-\d+\b", re.IGNORECASE)
_REFERENCE = re.compile(
    r"\b(?:payment|order|capture|reference)\s+([A-Za-z0-9][A-Za-z0-9_-]{5,})",
    re.IGNORECASE,
)


@dataclass
class ModelTurn:
    answer: str | None = None
    tool_name: str | None = None
    arguments: dict[str, object] | None = None


Model = Callable[[list[dict[str, object]]], ModelTurn]


def _function(name: str, description: str, properties: dict[str, object], required: list[str]) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


_PAYMENT_ID = {"type": "string", "description": "Payment id from the merchant message."}

TOOL_SPECS: list[dict[str, object]] = [
    _function(
        "find_payment",
        "Search this merchant for a payment by id or PayPal reference.",
        {
            "query": {"type": "string", "description": "Payment id or PayPal order or capture id."},
            "payment_id": _PAYMENT_ID,
        },
        [],
    ),
    _function("list_recent_payments", "List the latest payments for this merchant.", {}, []),
    _function(
        "create_test_order",
        "Create a catalog test order. The server sets the amount and currency.",
        {"test_order_code": {"type": "string", "description": "Catalog code such as DEMO-25."}},
        ["test_order_code"],
    ),
    _function(
        "complete_approved_payment",
        "Capture a payment the buyer has already approved.",
        {"payment_id": _PAYMENT_ID},
        ["payment_id"],
    ),
    _function(
        "investigate_payment",
        "Read the latest PayPal status for a payment and store the fact sheet.",
        {"payment_id": _PAYMENT_ID},
        ["payment_id"],
    ),
    _function(
        "prepare_refund_request",
        "Prepare a refund draft. This does not send the refund to PayPal.",
        {
            "payment_id": _PAYMENT_ID,
            "amount_minor": {"type": "integer", "description": "Refund amount in minor units."},
            "currency": {"type": "string"},
            "reason": {"type": "string"},
        },
        ["payment_id", "amount_minor", "currency", "reason"],
    ),
    _function(
        "check_operation_status",
        "Read the stored payment status without a new PayPal call.",
        {"payment_id": _PAYMENT_ID},
        ["payment_id"],
    ),
]

SYSTEM_PROMPT = """You are the PayFlow Guardian assistant for a PayPal Sandbox merchant.

You may call only these tools: find_payment, list_recent_payments, create_test_order, complete_approved_payment, investigate_payment, prepare_refund_request, check_operation_status.

When the merchant asks to investigate, check, refresh, or explain a payment, call investigate_payment with the payment id in the message before you answer. That tool reads PayPal.

Use find_payment when the merchant gives a PayPal reference and no payment id. Use list_recent_payments when they ask for recent payments and name no payment.

Never approve, reject, or send a refund. You have no tool for those actions. If the merchant asks you to approve or send a refund, refuse and say the owner must review the draft.

Call one tool at a time. After a tool result, explain only that result. Do not state a status, amount, currency, or PayPal id that the result does not contain. If confirmation is not confirmed, say PayPal has not confirmed the payment. Do not call the payment completed in that case.

Amounts in tool results are minor units. 2500 USD means 25.00 USD. Preparing a refund does not send it to PayPal."""


def default_model(history: list[dict[str, object]]) -> ModelTurn:
    """Choose an allowlisted tool from the merchant message, then explain the result."""
    user_text = _user_text(history)
    tool_turns = [item for item in history if item.get("role") == "tool"]
    if not tool_turns:
        return _plan(user_text)
    return _after_tool(user_text, tool_turns)


def model_for_settings(settings: Settings) -> Model:
    if settings.ai_api_key and settings.ai_base_url and settings.ai_model:
        return build_live_model(settings)
    return default_model


def build_live_model(settings: Settings, *, transport: httpx.BaseTransport | None = None) -> Model:
    def _model(history: list[dict[str, object]]) -> ModelTurn:
        try:
            return _complete(settings, history, transport)
        except Exception as exc:
            logger.info("assistant model unavailable error=%s", type(exc).__name__)
            return ModelTurn(answer=UNAVAILABLE)

    return _model


def _complete(
    settings: Settings,
    history: list[dict[str, object]],
    transport: httpx.BaseTransport | None,
) -> ModelTurn:
    payload = {
        "model": settings.ai_model,
        "messages": _provider_messages(history),
        "tools": TOOL_SPECS,
        "tool_choice": "auto",
    }
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    with httpx.Client(timeout=httpx.Timeout(30.0), transport=transport, follow_redirects=False) as client:
        response = client.post(
            _chat_url(settings.ai_base_url),
            headers={
                "Authorization": f"Bearer {settings.ai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"model http {response.status_code}")
    return _turn_from_body(response.json())


def _chat_url(base: str) -> str:
    trimmed = base.strip().rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    return f"{trimmed}/chat/completions"


def _provider_messages(history: list[dict[str, object]]) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    call_index = 0
    for item in history:
        role = item.get("role")
        if role == "user":
            content = item.get("content")
            messages.append({"role": "user", "content": content if isinstance(content, str) else ""})
            continue
        if role != "tool":
            continue
        call_index += 1
        name = item.get("tool_name") if isinstance(item.get("tool_name"), str) else "tool"
        call_id = f"call_{call_index}"
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": name, "arguments": "{}"},
                    }
                ],
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(item.get("content")),
            }
        )
    return messages


def _turn_from_body(body: object) -> ModelTurn:
    if not isinstance(body, dict):
        raise RuntimeError("model body")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise RuntimeError("model choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RuntimeError("model message")
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        legacy = message.get("function_call")
        if isinstance(legacy, dict):
            tool_calls = [{"function": legacy}]
        else:
            tool_calls = []
    if tool_calls and isinstance(tool_calls[0], dict):
        function = tool_calls[0].get("function")
        if not isinstance(function, dict):
            raise RuntimeError("model function")
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RuntimeError("model tool name")
        return ModelTurn(tool_name=name.strip(), arguments=_arguments(function.get("arguments")))
    content = _text_content(message.get("content"))
    if content:
        return ModelTurn(answer=content)
    raise RuntimeError("model empty")


def _text_content(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "".join(parts).strip()


def _arguments(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _user_text(history: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for item in history:
        if item.get("role") == "user" and isinstance(item.get("content"), str):
            parts.append(item["content"])
    return "\n".join(parts)


def _plan(user_text: str) -> ModelTurn:
    lowered = user_text.lower()
    payment_id = _payment_uuid(user_text)
    if _asks_to_send(lowered):
        return ModelTurn(
            answer="I cannot approve or send a refund. The owner reviews the draft and chooses Approve and send."
        )
    if _asks_to_prepare(lowered):
        return _plan_prepare(user_text, payment_id)
    if _asks_to_create(lowered):
        return _plan_create(user_text)
    if _asks_to_capture(lowered) and payment_id:
        return ModelTurn(tool_name="complete_approved_payment", arguments={"payment_id": payment_id})
    if _asks_to_list(lowered) and not _asks_to_investigate(lowered):
        return ModelTurn(tool_name="list_recent_payments", arguments={})
    if _asks_to_investigate(lowered) or payment_id:
        if payment_id:
            return ModelTurn(tool_name="investigate_payment", arguments={"payment_id": payment_id})
        reference = _labeled_reference(user_text)
        if reference:
            return ModelTurn(tool_name="find_payment", arguments={"query": reference})
        return ModelTurn(tool_name="list_recent_payments", arguments={})
    return ModelTurn(
        answer="I can look up a test payment, investigate it with PayPal, or prepare a refund for the owner to approve."
    )


def _after_tool(user_text: str, tool_turns: list[dict[str, object]]) -> ModelTurn:
    last = tool_turns[-1]
    name = last.get("tool_name") if isinstance(last.get("tool_name"), str) else ""
    result = last.get("content")
    if not isinstance(result, dict):
        return ModelTurn(answer="I could not read the payment result.")
    error = result.get("error")
    if error:
        message = result.get("message")
        if isinstance(message, str) and message.strip():
            return ModelTurn(answer=message.strip())
        return ModelTurn(answer="That action could not be completed.")
    investigated = any(item.get("tool_name") == "investigate_payment" for item in tool_turns)
    if not investigated and _asks_to_investigate(user_text.lower()):
        payment_id = _payment_id_from_result(result)
        if payment_id:
            return ModelTurn(tool_name="investigate_payment", arguments={"payment_id": payment_id})
    return ModelTurn(answer=_explain(name, result))


def _asks_to_send(lowered: str) -> bool:
    if re.search(r"\bprepare\b", lowered):
        return False
    if "approve and send" in lowered:
        return True
    if re.search(r"\bsend\b", lowered) and "refund" in lowered:
        return True
    return bool(re.search(r"\bapprove\b", lowered) and "refund" in lowered)


def _asks_to_prepare(lowered: str) -> bool:
    return "refund" in lowered and bool(re.search(r"\b(prepare|draft)\b", lowered))


def _asks_to_create(lowered: str) -> bool:
    if _CODE.search(lowered):
        return "refund" not in lowered
    return bool(re.search(r"\b(create|new)\b", lowered) and "order" in lowered)


def _asks_to_capture(lowered: str) -> bool:
    if "refund" in lowered:
        return False
    if re.search(r"\bcapture\b", lowered):
        return True
    return bool(re.search(r"\bcomplete(?: the)? (?:approved |the )?payment\b", lowered))


def _asks_to_list(lowered: str) -> bool:
    return bool(re.search(r"\b(list|recent|latest)\b", lowered) and "payment" in lowered)


def _asks_to_investigate(lowered: str) -> bool:
    return bool(re.search(r"\b(investigat\w*|check|lookup|look up|refresh|status|explain)\b", lowered))


def _plan_create(user_text: str) -> ModelTurn:
    match = _CODE.search(user_text)
    if match is None:
        return ModelTurn(answer="A catalog code is required. DEMO-25 is 25.00 USD and DEMO-49 is 49.00 USD.")
    return ModelTurn(tool_name="create_test_order", arguments={"test_order_code": match.group(0).upper()})


def _plan_prepare(user_text: str, payment_id: str | None) -> ModelTurn:
    amount = _amount_minor(user_text)
    reason = _reason(user_text)
    if payment_id is None or amount is None or reason is None:
        return ModelTurn(
            answer=(
                "To prepare a refund I need the payment, an amount, a currency, and a reason. "
                "Preparing a refund does not send it."
            )
        )
    minor, currency = amount
    return ModelTurn(
        tool_name="prepare_refund_request",
        arguments={
            "payment_id": payment_id,
            "amount_minor": minor,
            "currency": currency,
            "reason": reason,
        },
    )


def _explain(name: str, result: dict[str, object]) -> str:
    if name == "list_recent_payments":
        payments = result.get("payments")
        count = len(payments) if isinstance(payments, list) else 0
        if count == 0:
            return "There are no payments for this shop yet."
        return f"I found {count} recent payments. Name one and I can investigate it with PayPal."
    if name == "prepare_refund_request":
        return "The refund draft is waiting for the owner. It has not been sent to PayPal."
    if name == "create_test_order":
        amount = _amount_text(result.get("amount_minor"), result.get("currency"))
        return f"The test order is saved for {amount}. The amount comes from the catalog."
    confirmation = result.get("confirmation")
    status = result.get("status") if isinstance(result.get("status"), str) else "unknown"
    amount = _amount_text(result.get("amount_minor"), result.get("currency"))
    reference = result.get("paypal_capture_id") or result.get("paypal_order_id") or "no PayPal reference yet"
    if not isinstance(reference, str) or not reference:
        reference = "no PayPal reference yet"
    if confirmation != "confirmed":
        return (
            f"PayPal has not confirmed this payment. The stored status is {status}. "
            f"The amount on the payment is {amount}. Reference {reference}. "
            "It needs a check before another action."
        )
    if status == "completed":
        return f"PayPal confirmed this payment as completed. Amount {amount}. PayPal reference {reference}."
    if status == "awaiting_payer":
        return f"PayPal is waiting for the buyer to approve this payment. Amount {amount}. Reference {reference}."
    if status == "failed":
        return f"PayPal confirmed this payment as failed. Amount {amount}. Reference {reference}."
    return f"PayPal confirmed the stored status {status}. Amount {amount}. Reference {reference}."


def _payment_uuid(text: str) -> str | None:
    match = _UUID.search(text)
    if match is None:
        return None
    return match.group(0)


def _labeled_reference(text: str) -> str | None:
    match = _REFERENCE.search(text)
    if match is None:
        return None
    token = match.group(1)
    if _UUID.fullmatch(token):
        return None
    return token


def _payment_id_from_result(result: dict[str, object]) -> str | None:
    payment_id = result.get("payment_id")
    if isinstance(payment_id, str) and payment_id:
        return payment_id
    payments = result.get("payments")
    if isinstance(payments, list) and len(payments) == 1 and isinstance(payments[0], dict):
        only = payments[0].get("payment_id")
        if isinstance(only, str) and only:
            return only
    return None


def _amount_minor(text: str) -> tuple[int, str] | None:
    match = re.search(r"\b(\d{1,7})(?:\.(\d{2}))?\s*(USD|EUR|GBP)\b", text, re.IGNORECASE)
    if match is None:
        return None
    cents = match.group(2) or "00"
    return int(match.group(1)) * 100 + int(cents), match.group(3).upper()


def _reason(text: str) -> str | None:
    match = re.search(r"(?:because|reason:?)\s+(.+)$", text, re.IGNORECASE | re.DOTALL)
    if match is None:
        return None
    reason = " ".join(match.group(1).split())
    return reason[:500] or None


def _amount_text(amount_minor: object, currency: object) -> str:
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
        amount = "an unknown amount"
    else:
        whole, cents = divmod(amount_minor, 100)
        amount = f"{whole}.{cents:02d}"
    code = currency if isinstance(currency, str) else ""
    return f"{amount} {code}".strip()
