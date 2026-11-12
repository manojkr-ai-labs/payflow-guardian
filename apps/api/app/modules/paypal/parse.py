from __future__ import annotations

from dataclasses import dataclass

from app.modules.paypal.money import paypal_to_minor


@dataclass(frozen=True, slots=True)
class ParsedResource:
    paypal_order_id: str | None = None
    paypal_capture_id: str | None = None
    paypal_refund_id: str | None = None
    paypal_status: str | None = None
    amount_minor: int | None = None
    currency: str | None = None
    approve_url: str | None = None


def text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def as_dict(value: object) -> dict | None:
    if isinstance(value, dict):
        return value
    return None


def error_parts(body: object) -> tuple[str | None, str | None]:
    data = as_dict(body)
    if data is None:
        return None, None
    issue = None
    description = None
    details = data.get("details")
    if isinstance(details, list) and details:
        first = as_dict(details[0])
        if first is not None:
            issue = text(first.get("issue"))
            description = text(first.get("description"))
    message = description or text(data.get("message")) or text(data.get("name"))
    return issue, message


def approve_url(body: dict) -> str | None:
    links = body.get("links")
    if not isinstance(links, list):
        return None
    found: dict[str, str] = {}
    for link in links:
        item = as_dict(link)
        if item is None:
            continue
        rel = text(item.get("rel"))
        href = text(item.get("href"))
        if rel and href:
            found[rel] = href
    return found.get("approve") or found.get("payer-action")


def _amount(node: object) -> tuple[int | None, str | None]:
    body = as_dict(node)
    if body is None:
        return None, None
    amount = as_dict(body.get("amount"))
    if amount is None:
        return None, None
    currency = text(amount.get("currency_code"))
    raw_value = amount.get("value")
    if currency is None or not isinstance(raw_value, str):
        return None, currency
    return paypal_to_minor(raw_value, currency), currency


def _purchase_unit(body: dict) -> dict | None:
    units = body.get("purchase_units")
    if not isinstance(units, list) or not units:
        return None
    return as_dict(units[0])


def _captures(body: dict) -> list[dict]:
    unit = _purchase_unit(body)
    if unit is None:
        return []
    payments = as_dict(unit.get("payments"))
    if payments is None:
        return []
    captures = payments.get("captures")
    if not isinstance(captures, list):
        return []
    return [item for item in captures if isinstance(item, dict)]


def parse_order(body: dict) -> ParsedResource:
    capture = _captures(body)
    latest = capture[-1] if capture else None
    amount_minor, currency = _amount(latest) if latest else _amount(_purchase_unit(body))
    status = text(latest.get("status")) if latest else None
    if status is None:
        status = text(body.get("status"))
    return ParsedResource(
        paypal_order_id=text(body.get("id")),
        paypal_capture_id=text(latest.get("id")) if latest else None,
        paypal_status=status,
        amount_minor=amount_minor,
        currency=currency,
        approve_url=approve_url(body),
    )


def parse_capture_resource(body: dict) -> ParsedResource:
    amount_minor, currency = _amount(body)
    related = as_dict(body.get("supplementary_data"))
    related_ids = as_dict(related.get("related_ids")) if related else None
    order_id = text(related_ids.get("order_id")) if related_ids else None
    return ParsedResource(
        paypal_order_id=order_id,
        paypal_capture_id=text(body.get("id")),
        paypal_status=text(body.get("status")),
        amount_minor=amount_minor,
        currency=currency,
    )


def parse_refund(body: dict) -> ParsedResource:
    amount_minor, currency = _amount(body)
    return ParsedResource(
        paypal_refund_id=text(body.get("id")),
        paypal_status=text(body.get("status")),
        amount_minor=amount_minor,
        currency=currency,
    )


def build_order_body(value: str, currency: str, return_url: str, cancel_url: str) -> dict:
    return {
        "intent": "CAPTURE",
        "purchase_units": [{"amount": {"currency_code": currency, "value": value}}],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                    "user_action": "PAY_NOW",
                    "landing_page": "LOGIN",
                    "shipping_preference": "NO_SHIPPING",
                }
            }
        },
    }


def build_refund_body(value: str, currency: str) -> dict:
    return {"amount": {"currency_code": currency, "value": value}}
