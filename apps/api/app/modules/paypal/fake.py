from __future__ import annotations

from app.modules.paypal.money import require_money
from app.modules.paypal.types import CONFIRMED, PayPalCall


class FakePayPalAdapter:
    """In-memory PayPal stand-in. It records calls and never opens a socket."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._queue: dict[str, list[PayPalCall]] = {
            "create_order": [],
            "capture_order": [],
            "get_order_or_capture": [],
            "refund_capture": [],
        }
        self._sequence = 0

    def queue(self, operation: str, result: PayPalCall) -> FakePayPalAdapter:
        if operation not in self._queue:
            raise ValueError(f"Unknown PayPal operation: {operation}")
        self._queue[operation].append(result)
        return self

    def create_order(
        self,
        amount_minor: int,
        currency: str,
        return_url: str,
        cancel_url: str,
    ) -> PayPalCall:
        code = require_money(amount_minor, currency)
        self.calls.append(
            {
                "operation": "create_order",
                "amount_minor": amount_minor,
                "currency": code,
                "return_url": return_url,
                "cancel_url": cancel_url,
            }
        )
        queued = self._pop("create_order")
        if queued is not None:
            return queued
        order_id = self._next_id("FAKE-ORDER")
        return PayPalCall(
            operation="create_order",
            status="awaiting_payer",
            confirmation=CONFIRMED,
            paypal_status="PAYER_ACTION_REQUIRED",
            http_status=201,
            paypal_order_id=order_id,
            approve_url=f"https://example.test/paypal/approve/{order_id}",
            amount_minor=amount_minor,
            currency=code,
        )

    def capture_order(self, paypal_order_id: str) -> PayPalCall:
        order_id = paypal_order_id.strip()
        self.calls.append({"operation": "capture_order", "paypal_order_id": order_id})
        queued = self._pop("capture_order")
        if queued is not None:
            return queued
        return PayPalCall(
            operation="capture_order",
            status="completed",
            confirmation=CONFIRMED,
            paypal_status="COMPLETED",
            http_status=201,
            paypal_order_id=order_id,
            paypal_capture_id=self._next_id("FAKE-CAPTURE"),
            amount_minor=None,
            currency=None,
        )

    def get_order_or_capture(
        self,
        paypal_order_id: str | None = None,
        paypal_capture_id: str | None = None,
    ) -> PayPalCall:
        self.calls.append(
            {
                "operation": "get_order_or_capture",
                "paypal_order_id": paypal_order_id,
                "paypal_capture_id": paypal_capture_id,
            }
        )
        queued = self._pop("get_order_or_capture")
        if queued is not None:
            return queued
        if not (paypal_order_id or paypal_capture_id):
            raise ValueError("A PayPal order id or capture id is required")
        return PayPalCall(
            operation="get_order_or_capture",
            status="completed" if paypal_capture_id else "awaiting_payer",
            confirmation=CONFIRMED,
            paypal_status="COMPLETED" if paypal_capture_id else "PAYER_ACTION_REQUIRED",
            http_status=200,
            paypal_order_id=paypal_order_id,
            paypal_capture_id=paypal_capture_id,
        )

    def refund_capture(
        self,
        capture_id: str,
        amount_minor: int,
        currency: str,
        request_id: str,
    ) -> PayPalCall:
        code = require_money(amount_minor, currency)
        self.calls.append(
            {
                "operation": "refund_capture",
                "capture_id": capture_id,
                "amount_minor": amount_minor,
                "currency": code,
                "request_id": request_id,
            }
        )
        queued = self._pop("refund_capture")
        if queued is not None:
            return queued
        return PayPalCall(
            operation="refund_capture",
            status="completed",
            confirmation=CONFIRMED,
            paypal_status="COMPLETED",
            http_status=201,
            paypal_capture_id=capture_id,
            paypal_refund_id=self._next_id("FAKE-REFUND"),
            amount_minor=amount_minor,
            currency=code,
        )

    def _pop(self, operation: str) -> PayPalCall | None:
        queued = self._queue[operation]
        if not queued:
            return None
        return queued.pop(0)

    def _next_id(self, prefix: str) -> str:
        self._sequence += 1
        return f"{prefix}-{self._sequence}"
