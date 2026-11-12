from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

CONFIRMED = "confirmed"
UNCONFIRMED = "unconfirmed"
PAYPAL_FAILED = "paypal_failed"
NEEDS_CHECKING = "needs_checking"


@dataclass(frozen=True, slots=True)
class PayPalCall:
    """One adapter result. Tokens and secrets are never fields on this object."""

    operation: str
    status: str
    confirmation: str
    paypal_status: str | None = None
    http_status: int | None = None
    error_code: str | None = None
    message: str = ""
    issue: str | None = None
    paypal_order_id: str | None = None
    paypal_capture_id: str | None = None
    paypal_refund_id: str | None = None
    approve_url: str | None = None
    amount_minor: int | None = None
    currency: str | None = None


@runtime_checkable
class PayPalAdapter(Protocol):
    def create_order(
        self,
        amount_minor: int,
        currency: str,
        return_url: str,
        cancel_url: str,
    ) -> PayPalCall: ...

    def capture_order(self, paypal_order_id: str) -> PayPalCall: ...

    def get_order_or_capture(
        self,
        paypal_order_id: str | None = None,
        paypal_capture_id: str | None = None,
    ) -> PayPalCall: ...

    def refund_capture(
        self,
        capture_id: str,
        amount_minor: int,
        currency: str,
        request_id: str,
    ) -> PayPalCall: ...
