from __future__ import annotations

from app.modules.paypal.types import CONFIRMED, NEEDS_CHECKING, UNCONFIRMED

# PayPal status string -> local status. Unknown strings stay needs_checking.
_STATUS_MAP = {
    "CREATED": "awaiting_payer",
    "SAVED": "created",
    "PAYER_ACTION_REQUIRED": "awaiting_payer",
    "APPROVED": "pending",
    "VOIDED": "failed",
    "COMPLETED": "completed",
    "PENDING": "pending",
    "FAILED": "failed",
    "DECLINED": "failed",
    "DENIED": "failed",
    "REFUNDED": "refunded",
    "PARTIALLY_REFUNDED": "partially_refunded",
    "CANCELLED": "failed",
    "CANCELED": "failed",
}

# These local statuses describe captured money, so they need a capture id.
_CAPTURE_REQUIRED = frozenset({"completed", "refunded", "partially_refunded"})


def map_paypal_status(paypal_status: str | None, *, paypal_id: str | None) -> tuple[str, str]:
    """Map a PayPal status onto the local status and confirmation pair.

    A confirmed result requires a recognized status and a PayPal id. Anything else
    is needs_checking and unconfirmed.
    """
    if not paypal_id or not isinstance(paypal_status, str) or not paypal_status.strip():
        return NEEDS_CHECKING, UNCONFIRMED
    local = _STATUS_MAP.get(paypal_status.strip().upper())
    if local is None:
        return NEEDS_CHECKING, UNCONFIRMED
    return local, CONFIRMED


def confirm_payment_status(
    paypal_status: str | None,
    *,
    order_id: str | None,
    capture_id: str | None,
) -> tuple[str, str]:
    """Confirm an order or capture. Completed money needs a capture id."""
    local, confirmation = map_paypal_status(paypal_status, paypal_id=capture_id or order_id)
    if confirmation != CONFIRMED:
        return NEEDS_CHECKING, UNCONFIRMED
    if local in _CAPTURE_REQUIRED and not capture_id:
        return NEEDS_CHECKING, UNCONFIRMED
    if local == "pending" and not capture_id and (paypal_status or "").strip().upper() != "APPROVED":
        return NEEDS_CHECKING, UNCONFIRMED
    return local, confirmation
