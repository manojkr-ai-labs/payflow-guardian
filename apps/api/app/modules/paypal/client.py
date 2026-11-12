from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.modules.paypal.money import minor_to_paypal, require_money
from app.modules.paypal.parse import (
    as_dict,
    build_order_body,
    build_refund_body,
    error_parts,
    parse_capture_resource,
    parse_order,
    parse_refund,
    text,
)
from app.modules.paypal.status import confirm_payment_status, map_paypal_status
from app.modules.paypal.types import NEEDS_CHECKING, PAYPAL_FAILED, UNCONFIRMED, PayPalCall

logger = logging.getLogger("app.paypal")

REFRESH_SKEW_SECONDS = 60
PAYER_STILL_REQUIRED = frozenset({"ORDER_NOT_APPROVED", "PAYER_ACTION_REQUIRED"})
ALREADY_SENT = frozenset({"ORDER_ALREADY_CAPTURED", "ORDER_ALREADY_AUTHORIZED"})


class _TransportFailure(Exception):
    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(kind)


class TokenCache:
    """Process memory for one access token. The token is not logged or stored elsewhere."""

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_after = 0.0
        self._lock = threading.Lock()

    def get(self, now: float) -> str | None:
        with self._lock:
            if self._access_token is None or now >= self._refresh_after:
                return None
            return self._access_token

    def store(self, access_token: str, expires_in: int, now: float) -> None:
        skew = _refresh_skew(expires_in)
        with self._lock:
            self._access_token = access_token
            self._refresh_after = now + expires_in - skew

    def invalidate(self) -> None:
        with self._lock:
            self._access_token = None
            self._refresh_after = 0.0


def _refresh_skew(expires_in: int) -> int:
    if expires_in <= 1:
        return 0
    return min(REFRESH_SKEW_SECONDS, max(1, expires_in // 10))


def _expires_in(body: dict | None) -> int | None:
    if body is None:
        return None
    raw = body.get("expires_in")
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _json_object(response: httpx.Response) -> dict | None:
    try:
        body = response.json()
    except ValueError:
        return None
    return as_dict(body)


class PayPalClient:
    """PayPal Sandbox HTTP adapter. Callers outside this module do not receive a token."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._client_id = settings.paypal_client_id
        self._client_secret = settings.paypal_client_secret
        self._api_base = settings.paypal_api_base.rstrip("/")
        self._now = clock or time.time
        self._tokens = TokenCache()
        self._token_lock = threading.Lock()
        self._http = httpx.Client(
            base_url=self._api_base,
            transport=transport,
            timeout=httpx.Timeout(20.0),
            follow_redirects=False,
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    def __repr__(self) -> str:
        return f"PayPalClient(api_base={self._api_base!r})"

    def close(self) -> None:
        self._http.close()

    def token_is_cached(self) -> bool:
        return self._tokens.get(self._now()) is not None

    def create_order(
        self,
        amount_minor: int,
        currency: str,
        return_url: str,
        cancel_url: str,
    ) -> PayPalCall:
        code = require_money(amount_minor, currency)
        _require_url(return_url)
        _require_url(cancel_url)
        body = build_order_body(minor_to_paypal(amount_minor, code), code, return_url, cancel_url)
        outcome = self._exchange("create_order", "POST", "/v2/checkout/orders", json_body=body)
        if isinstance(outcome, PayPalCall):
            return outcome
        result = self._interpret_order("create_order", outcome)
        self._log_result("create_order", outcome.status_code, result)
        return result

    def capture_order(self, paypal_order_id: str) -> PayPalCall:
        order_id = _require_reference(paypal_order_id, "paypal_order_id")
        path = f"/v2/checkout/orders/{quote(order_id, safe='')}/capture"
        outcome = self._exchange("capture_order", "POST", path, json_body={})
        if isinstance(outcome, PayPalCall):
            return _remember_order(outcome, order_id)
        result = _remember_order(self._interpret_order("capture_order", outcome), order_id)
        self._log_result("capture_order", outcome.status_code, result)
        return result

    def get_order_or_capture(
        self,
        paypal_order_id: str | None = None,
        paypal_capture_id: str | None = None,
    ) -> PayPalCall:
        capture_id = paypal_capture_id.strip() if isinstance(paypal_capture_id, str) else ""
        order_id = paypal_order_id.strip() if isinstance(paypal_order_id, str) else ""
        if capture_id:
            path = f"/v2/payments/captures/{quote(capture_id, safe='')}"
            outcome = self._exchange("get_order_or_capture", "GET", path)
            if isinstance(outcome, PayPalCall):
                return _remember_capture(outcome, capture_id, order_id or None)
            result = self._interpret_capture_resource(outcome, order_id or None)
            self._log_result("get_order_or_capture", outcome.status_code, result)
            return result
        if order_id:
            path = f"/v2/checkout/orders/{quote(order_id, safe='')}"
            outcome = self._exchange("get_order_or_capture", "GET", path)
            if isinstance(outcome, PayPalCall):
                return _remember_order(outcome, order_id)
            result = _remember_order(self._interpret_order("get_order_or_capture", outcome), order_id)
            self._log_result("get_order_or_capture", outcome.status_code, result)
            return result
        raise ValueError("A PayPal order id or capture id is required")

    def refund_capture(
        self,
        capture_id: str,
        amount_minor: int,
        currency: str,
        request_id: str,
    ) -> PayPalCall:
        capture = _require_reference(capture_id, "capture_id")
        code = require_money(amount_minor, currency)
        if amount_minor <= 0:
            raise ValueError("refund amount_minor must be greater than zero")
        request = _require_request_id(request_id)
        path = f"/v2/payments/captures/{quote(capture, safe='')}/refund"
        body = build_refund_body(minor_to_paypal(amount_minor, code), code)
        outcome = self._exchange(
            "refund_capture",
            "POST",
            path,
            json_body=body,
            extra_headers={"PayPal-Request-Id": request},
        )
        if isinstance(outcome, PayPalCall):
            return _remember_capture(outcome, capture, None)
        result = _remember_capture(self._interpret_refund(outcome), capture, None)
        self._log_result("refund_capture", outcome.status_code, result)
        return result

    def _bearer(self, *, force: bool) -> str | PayPalCall:
        if not force:
            cached = self._tokens.get(self._now())
            if cached is not None:
                return cached
        with self._token_lock:
            if not force:
                cached = self._tokens.get(self._now())
                if cached is not None:
                    return cached
            if force:
                self._tokens.invalidate()
            return self._fetch_token()

    def _fetch_token(self) -> str | PayPalCall:
        try:
            response = self._http.post(
                "/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                headers={"Accept": "application/json", "Accept-Language": "en_US"},
            )
        except httpx.TimeoutException:
            self._log("token", "timeout")
            return _unclear("token", "PayPal did not answer the token request.")
        except httpx.TransportError:
            self._log("token", "transport_error")
            return _unclear("token", "PayPal did not answer the token request.")
        self._log("token", response.status_code)
        if response.status_code != 200:
            if response.status_code in {400, 401, 403}:
                return PayPalCall(
                    operation="token",
                    status="failed",
                    confirmation=UNCONFIRMED,
                    http_status=response.status_code,
                    error_code=PAYPAL_FAILED,
                    message="PayPal rejected the Sandbox credentials.",
                )
            return _unclear(
                "token",
                "PayPal could not issue an access token.",
                http_status=response.status_code,
            )
        body = _json_object(response)
        token = text(body.get("access_token")) if body else None
        expires_in = _expires_in(body)
        if not token or expires_in is None:
            return _unclear("token", "PayPal returned an incomplete token response.", http_status=200)
        self._tokens.store(token, expires_in, self._now())
        return token

    def _exchange(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response | PayPalCall:
        token = self._bearer(force=False)
        if isinstance(token, PayPalCall):
            return _retarget(token, operation)
        try:
            response = self._send(method, path, token, json_body, extra_headers)
        except _TransportFailure as exc:
            self._log(operation, exc.kind)
            return _unclear(operation, "PayPal did not answer. The payment needs a check.")
        if response.status_code != 401:
            return response
        self._log(operation, 401)
        refreshed = self._bearer(force=True)
        if isinstance(refreshed, PayPalCall):
            return _retarget(refreshed, operation)
        try:
            retried = self._send(method, path, refreshed, json_body, extra_headers)
        except _TransportFailure as exc:
            self._log(operation, exc.kind)
            return _unclear(operation, "PayPal did not answer. The payment needs a check.")
        if retried.status_code == 401:
            self._log(operation, 401)
            return PayPalCall(
                operation=operation,
                status="failed",
                confirmation=UNCONFIRMED,
                http_status=401,
                error_code=PAYPAL_FAILED,
                message="PayPal rejected the access token.",
            )
        return retried

    def _send(
        self,
        method: str,
        path: str,
        token: str,
        json_body: dict | None,
        extra_headers: dict[str, str] | None,
    ) -> httpx.Response:
        headers = {
            "Accept": "application/json",
            "Prefer": "return=representation",
        }
        if extra_headers:
            headers.update(extra_headers)
        headers["Authorization"] = f"Bearer {token}"
        try:
            return self._http.request(method, path, json=json_body, headers=headers)
        except httpx.TimeoutException:
            raise _TransportFailure("timeout") from None
        except httpx.TransportError:
            raise _TransportFailure("transport_error") from None

    def _interpret_order(self, operation: str, response: httpx.Response) -> PayPalCall:
        blocked = self._blocked(operation, response)
        if blocked is not None:
            return blocked
        body = _json_object(response)
        if body is None:
            return _unclear(operation, "PayPal returned an incomplete result.", http_status=response.status_code)
        parsed = parse_order(body)
        local, confirmation = confirm_payment_status(
            parsed.paypal_status,
            order_id=parsed.paypal_order_id,
            capture_id=parsed.paypal_capture_id,
        )
        recognized = confirmation != UNCONFIRMED
        return PayPalCall(
            operation=operation,
            status=local,
            confirmation=confirmation,
            paypal_status=parsed.paypal_status,
            http_status=response.status_code,
            error_code=None if recognized else NEEDS_CHECKING,
            message="" if recognized else _unclear_message(parsed.paypal_status),
            paypal_order_id=parsed.paypal_order_id,
            paypal_capture_id=parsed.paypal_capture_id,
            approve_url=parsed.approve_url,
            amount_minor=parsed.amount_minor,
            currency=parsed.currency,
        )

    def _interpret_capture_resource(self, response: httpx.Response, order_id: str | None) -> PayPalCall:
        blocked = self._blocked("get_order_or_capture", response)
        if blocked is not None:
            return _remember_order(blocked, order_id or "")
        body = _json_object(response)
        if body is None:
            return _unclear(
                "get_order_or_capture",
                "PayPal returned an incomplete result.",
                http_status=response.status_code,
                paypal_order_id=order_id,
            )
        parsed = parse_capture_resource(body)
        resolved_order = parsed.paypal_order_id or order_id
        local, confirmation = confirm_payment_status(
            parsed.paypal_status,
            order_id=resolved_order,
            capture_id=parsed.paypal_capture_id,
        )
        recognized = confirmation != UNCONFIRMED
        return PayPalCall(
            operation="get_order_or_capture",
            status=local,
            confirmation=confirmation,
            paypal_status=parsed.paypal_status,
            http_status=response.status_code,
            error_code=None if recognized else NEEDS_CHECKING,
            message="" if recognized else _unclear_message(parsed.paypal_status),
            paypal_order_id=resolved_order,
            paypal_capture_id=parsed.paypal_capture_id,
            amount_minor=parsed.amount_minor,
            currency=parsed.currency,
        )

    def _interpret_refund(self, response: httpx.Response) -> PayPalCall:
        blocked = self._blocked("refund_capture", response)
        if blocked is not None:
            return blocked
        body = _json_object(response)
        if body is None:
            return _unclear(
                "refund_capture",
                "PayPal returned an incomplete result.",
                http_status=response.status_code,
            )
        parsed = parse_refund(body)
        local, confirmation = map_paypal_status(parsed.paypal_status, paypal_id=parsed.paypal_refund_id)
        recognized = confirmation != UNCONFIRMED
        return PayPalCall(
            operation="refund_capture",
            status=local,
            confirmation=confirmation,
            paypal_status=parsed.paypal_status,
            http_status=response.status_code,
            error_code=None if recognized else NEEDS_CHECKING,
            message="" if recognized else _unclear_message(parsed.paypal_status),
            paypal_refund_id=parsed.paypal_refund_id,
            amount_minor=parsed.amount_minor,
            currency=parsed.currency,
        )

    def _blocked(self, operation: str, response: httpx.Response) -> PayPalCall | None:
        code = response.status_code
        if code >= 500 or code == 408 or 300 <= code < 400:
            return PayPalCall(
                operation=operation,
                status=NEEDS_CHECKING,
                confirmation=UNCONFIRMED,
                http_status=code,
                error_code=NEEDS_CHECKING,
                message="PayPal returned an unclear result.",
            )
        if code >= 400:
            return self._explicit(operation, response)
        if code < 200:
            return _unclear(operation, "PayPal returned an unclear result.", http_status=code)
        return None

    def _explicit(self, operation: str, response: httpx.Response) -> PayPalCall:
        body = _json_object(response)
        issue, message = error_parts(body)
        safe = self._scrub(message or "PayPal rejected the request.")
        parsed = parse_order(body or {})
        if operation == "refund_capture":
            refund = parse_refund(body or {})
            parsed = replace(parsed, paypal_refund_id=refund.paypal_refund_id or parsed.paypal_refund_id)
        if issue in PAYER_STILL_REQUIRED:
            return PayPalCall(
                operation=operation,
                status="awaiting_payer",
                confirmation=UNCONFIRMED,
                http_status=response.status_code,
                error_code=None,
                message=safe,
                issue=issue,
                paypal_order_id=parsed.paypal_order_id,
            )
        if issue in ALREADY_SENT:
            return PayPalCall(
                operation=operation,
                status=NEEDS_CHECKING,
                confirmation=UNCONFIRMED,
                http_status=response.status_code,
                error_code=NEEDS_CHECKING,
                message=safe,
                issue=issue,
                paypal_order_id=parsed.paypal_order_id,
                paypal_capture_id=parsed.paypal_capture_id,
            )
        status = NEEDS_CHECKING if operation == "get_order_or_capture" else "failed"
        return PayPalCall(
            operation=operation,
            status=status,
            confirmation=UNCONFIRMED,
            http_status=response.status_code,
            error_code=PAYPAL_FAILED,
            message=safe,
            issue=issue,
            paypal_order_id=parsed.paypal_order_id,
            paypal_capture_id=parsed.paypal_capture_id,
            paypal_refund_id=parsed.paypal_refund_id,
        )

    def _scrub(self, value: str) -> str:
        cleaned = " ".join(value.split())
        if self._client_secret:
            cleaned = cleaned.replace(self._client_secret, "[redacted]")
        cached = self._tokens.get(self._now())
        if cached:
            cleaned = cleaned.replace(cached, "[redacted]")
        return cleaned[:240]

    def _log(self, operation: str, http_status: object) -> None:
        logger.info("paypal operation=%s http_status=%s", operation, http_status)

    def _log_result(self, operation: str, http_status: int, result: PayPalCall) -> None:
        logger.info(
            "paypal operation=%s http_status=%s paypal_order_id=%s paypal_capture_id=%s paypal_refund_id=%s",
            operation,
            http_status,
            result.paypal_order_id or "",
            result.paypal_capture_id or "",
            result.paypal_refund_id or "",
        )


def _unclear_message(paypal_status: str | None) -> str:
    if paypal_status:
        mapped, _confirmation = map_paypal_status(paypal_status, paypal_id="present")
        if mapped == NEEDS_CHECKING:
            return "PayPal returned a status that is not recognized."
    return "PayPal returned an incomplete result."


def _unclear(
    operation: str,
    message: str,
    *,
    http_status: int | None = None,
    paypal_order_id: str | None = None,
) -> PayPalCall:
    return PayPalCall(
        operation=operation,
        status=NEEDS_CHECKING,
        confirmation=UNCONFIRMED,
        http_status=http_status,
        error_code=NEEDS_CHECKING,
        message=message,
        paypal_order_id=paypal_order_id,
    )


def _retarget(result: PayPalCall, operation: str) -> PayPalCall:
    if result.operation == operation:
        return result
    return replace(result, operation=operation)


def _remember_order(result: PayPalCall, order_id: str) -> PayPalCall:
    if not order_id or result.paypal_order_id:
        return result
    return replace(result, paypal_order_id=order_id)


def _remember_capture(result: PayPalCall, capture_id: str, order_id: str | None) -> PayPalCall:
    current = result
    if capture_id and not current.paypal_capture_id:
        current = replace(current, paypal_capture_id=capture_id)
    if order_id and not current.paypal_order_id:
        current = replace(current, paypal_order_id=order_id)
    return current


def _require_url(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("return_url and cancel_url are required")


def _require_reference(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _require_request_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("request_id is required")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128:
        raise ValueError("request_id is required")
    if any(ord(char) < 32 or ord(char) > 126 for char in cleaned):
        raise ValueError("request_id must be printable ASCII")
    return cleaned


_client: PayPalClient | None = None
_client_lock = threading.Lock()


def get_paypal_client() -> PayPalClient:
    global _client
    with _client_lock:
        if _client is None:
            from app.core.db import get_settings

            _client = PayPalClient(get_settings())
        return _client
