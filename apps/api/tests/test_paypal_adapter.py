"""PayPal adapter checks. The HTTP stand-in never calls Sandbox.

Covers a cached token, a single 401 refresh, a known status, an unknown status,
and a timeout or HTTP 500 that does not repeat a capture or refund.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.paypal.client import PayPalClient
from app.modules.paypal.fake import FakePayPalAdapter
from app.modules.paypal.money import minor_to_paypal, paypal_to_minor
from app.modules.paypal.parse import approve_url
from app.modules.paypal.sandbox_check import credentials_present, fetch_token_status, main
from app.modules.paypal.status import confirm_payment_status, map_paypal_status
from app.modules.paypal.types import NEEDS_CHECKING, PAYPAL_FAILED, PayPalAdapter, PayPalCall, UNCONFIRMED

ROOT = Path(__file__).resolve().parents[3]
TOKEN = "memory-only-access-token"
SECRET = "test-client-secret"
RETURN_URL = "https://example.test/payments/pay_1/return"
CANCEL_URL = "https://example.test/payments/pay_1/cancel"

CAPTURED = {
    "id": "ORDER-1",
    "status": "COMPLETED",
    "purchase_units": [
        {
            "amount": {"currency_code": "USD", "value": "25.00"},
            "payments": {
                "captures": [
                    {
                        "id": "CAP-1",
                        "status": "COMPLETED",
                        "amount": {"currency_code": "USD", "value": "25.00"},
                    }
                ]
            },
        }
    ],
}


class Endpoint:
    def __init__(self) -> None:
        self.seen: list[httpx.Request] = []
        self._queued: dict[str, list[httpx.Response | Exception]] = {}

    def push(self, path_suffix: str, item: httpx.Response | Exception) -> None:
        self._queued.setdefault(path_suffix, []).append(item)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        for suffix, queued in self._queued.items():
            if request.url.path.endswith(suffix) and queued:
                item = queued.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item
        raise AssertionError(f"unexpected {request.method} {request.url.path}")


def _settings() -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        session_secret="test-session-secret",
        paypal_client_id="test-client-id",
        paypal_client_secret=SECRET,
        paypal_api_base="https://api-m.sandbox.paypal.com",
        web_origin="http://localhost:3000",
    )


def _client(endpoint: Endpoint, clock=None) -> PayPalClient:
    return PayPalClient(_settings(), transport=httpx.MockTransport(endpoint), clock=clock)


def _token(access_token: str = TOKEN, expires_in: int = 3600) -> httpx.Response:
    return httpx.Response(
        200,
        json={"access_token": access_token, "expires_in": expires_in, "token_type": "Bearer"},
    )


def _created(order_id: str = "ORDER-1") -> httpx.Response:
    return httpx.Response(
        201,
        json={
            "id": order_id,
            "status": "CREATED",
            "links": [{"rel": "payer-action", "href": f"https://example.test/approve/{order_id}", "method": "GET"}],
        },
    )


def _money_posts(endpoint: Endpoint) -> list[httpx.Request]:
    return [
        request
        for request in endpoint.seen
        if request.method == "POST" and request.url.path.endswith(("/capture", "/refund"))
    ]


def _database_text(db: Session) -> str:
    names = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars().all()
    chunks: list[str] = []
    for name in names:
        rows = db.execute(text(f'SELECT * FROM "{name}"')).all()
        chunks.append(repr(rows))
    return "\n".join(chunks)


def _assert_secrets_absent(text_value: str, *secrets: str) -> None:
    for secret in secrets:
        assert secret not in text_value
    assert "Authorization" not in text_value
    assert "Basic " not in text_value
    assert "Bearer " not in text_value
    assert "access_token" not in text_value


@pytest.mark.parametrize(
    ("paypal_status", "local_status"),
    [
        ("COMPLETED", "completed"),
        ("PENDING", "pending"),
        ("FAILED", "failed"),
        ("REFUNDED", "refunded"),
        ("PARTIALLY_REFUNDED", "partially_refunded"),
        ("PAYER_ACTION_REQUIRED", "awaiting_payer"),
        ("CREATED", "awaiting_payer"),
        ("SAVED", "created"),
        ("APPROVED", "pending"),
        ("VOIDED", "failed"),
        ("DECLINED", "failed"),
        ("CANCELLED", "failed"),
    ],
)
def test_known_paypal_status_is_confirmed_when_an_id_is_present(paypal_status: str, local_status: str) -> None:
    status, confirmation = map_paypal_status(paypal_status, paypal_id="PAYPAL-1")
    assert status == local_status
    assert confirmation == "confirmed"


def test_unknown_status_and_missing_id_stay_unconfirmed() -> None:
    unknown, unknown_confirmation = map_paypal_status("FROBNICATED", paypal_id="PAYPAL-1")
    assert unknown == NEEDS_CHECKING
    assert unknown_confirmation == UNCONFIRMED
    missing, missing_confirmation = map_paypal_status("COMPLETED", paypal_id=None)
    assert missing == NEEDS_CHECKING
    assert missing_confirmation == UNCONFIRMED
    incomplete, incomplete_confirmation = confirm_payment_status("COMPLETED", order_id="ORDER-1", capture_id=None)
    assert incomplete == NEEDS_CHECKING
    assert incomplete_confirmation == UNCONFIRMED


def test_classic_approve_link_is_used_ahead_of_checkoutweb() -> None:
    href = approve_url(
        {
            "links": [
                {
                    "rel": "payer-action",
                    "href": "https://www.sandbox.paypal.com/checkoutweb/signup?token=ORDER-1",
                },
                {"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER-1"},
            ]
        }
    )
    assert href == "https://www.sandbox.paypal.com/checkoutnow?token=ORDER-1"


def test_minor_units_cross_the_paypal_boundary_as_decimals() -> None:
    assert minor_to_paypal(2500, "USD") == "25.00"
    assert minor_to_paypal(5, "USD") == "0.05"
    assert minor_to_paypal(2500, "JPY") == "2500"
    assert paypal_to_minor("25.00", "USD") == 2500
    assert paypal_to_minor("25.5", "USD") == 2550


def test_token_stays_in_memory_and_out_of_logs_and_the_database(db: Session, caplog: pytest.LogCaptureFixture) -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token())
    endpoint.push("/v2/checkout/orders", _created())
    endpoint.push("/v2/checkout/orders", _created("ORDER-2"))
    caplog.set_level(logging.INFO, logger="app.paypal")
    client = _client(endpoint)
    try:
        first = client.create_order(2500, "USD", RETURN_URL, CANCEL_URL)
        assert client.token_is_cached() is True
        second = client.create_order(4900, "usd", RETURN_URL, CANCEL_URL)
    finally:
        client.close()

    assert first.status == "awaiting_payer"
    assert first.confirmation == "confirmed"
    assert first.paypal_order_id == "ORDER-1"
    assert first.approve_url == "https://example.test/approve/ORDER-1"
    assert second.paypal_order_id == "ORDER-2"
    token_calls = [request for request in endpoint.seen if request.url.path == "/v1/oauth2/token"]
    assert len(token_calls) == 1
    raw_auth = token_calls[0].headers["authorization"].split(" ", 1)[1]
    assert base64.b64decode(raw_auth).decode() == f"test-client-id:{SECRET}"
    order_bodies = [
        json.loads(request.content)
        for request in endpoint.seen
        if request.url.path == "/v2/checkout/orders"
    ]
    assert order_bodies[0]["purchase_units"][0]["amount"] == {"currency_code": "USD", "value": "25.00"}
    assert order_bodies[1]["purchase_units"][0]["amount"] == {"currency_code": "USD", "value": "49.00"}
    assert order_bodies[0]["payment_source"]["paypal"]["experience_context"]["return_url"] == RETURN_URL
    rendered = "\n".join(record.getMessage() for record in caplog.records)
    _assert_secrets_absent(rendered, TOKEN, SECRET)
    assert "http_status=200" in rendered
    assert "paypal_order_id=ORDER-1" in rendered
    stored = _database_text(db)
    assert TOKEN not in stored
    assert SECRET not in stored


def test_token_refreshes_shortly_before_expiry() -> None:
    now = [1000.0]
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token("token-early", expires_in=3600))
    endpoint.push("/v1/oauth2/token", _token("token-later", expires_in=3600))
    endpoint.push("/v2/checkout/orders", _created("ORDER-1"))
    endpoint.push("/v2/checkout/orders", _created("ORDER-2"))
    endpoint.push("/v2/checkout/orders", _created("ORDER-3"))
    client = _client(endpoint, clock=lambda: now[0])
    try:
        client.create_order(2500, "USD", RETURN_URL, CANCEL_URL)
        now[0] = 4539.0
        assert client.token_is_cached() is True
        client.create_order(2500, "USD", RETURN_URL, CANCEL_URL)
        now[0] = 4540.0
        assert client.token_is_cached() is False
        client.create_order(2500, "USD", RETURN_URL, CANCEL_URL)
    finally:
        client.close()
    token_calls = [request for request in endpoint.seen if request.url.path == "/v1/oauth2/token"]
    assert len(token_calls) == 2
    order_auths = [
        request.headers["authorization"]
        for request in endpoint.seen
        if request.url.path == "/v2/checkout/orders"
    ]
    assert order_auths == ["Bearer token-early", "Bearer token-early", "Bearer token-later"]


def test_401_refreshes_the_token_once_and_retries_the_call(caplog: pytest.LogCaptureFixture) -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token("token-aaa"))
    endpoint.push("/v1/oauth2/token", _token("token-bbb"))
    endpoint.push("/capture", httpx.Response(401, json={"error": "invalid_token", "access_token": "token-aaa"}))
    endpoint.push("/capture", httpx.Response(201, json=CAPTURED))
    caplog.set_level(logging.INFO, logger="app.paypal")
    client = _client(endpoint)
    try:
        result = client.capture_order("ORDER-1")
    finally:
        client.close()

    assert result.status == "completed"
    assert result.confirmation == "confirmed"
    assert result.paypal_capture_id == "CAP-1"
    assert result.paypal_order_id == "ORDER-1"
    assert result.amount_minor == 2500
    assert result.currency == "USD"
    assert result.paypal_status == "COMPLETED"
    assert result.error_code is None
    posts = _money_posts(endpoint)
    assert len(posts) == 2
    assert [request.headers["authorization"] for request in posts] == ["Bearer token-aaa", "Bearer token-bbb"]
    assert len([request for request in endpoint.seen if request.url.path == "/v1/oauth2/token"]) == 2
    rendered = "\n".join(record.getMessage() for record in caplog.records)
    _assert_secrets_absent(rendered, "token-aaa", "token-bbb", SECRET)
    assert "http_status=401" in rendered
    assert "paypal_capture_id=CAP-1" in rendered


def test_a_second_401_does_not_send_a_third_call(caplog: pytest.LogCaptureFixture) -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token("token-aaa"))
    endpoint.push("/v1/oauth2/token", _token("token-bbb"))
    endpoint.push("/capture", httpx.Response(401, json={"error": "invalid_token"}))
    endpoint.push("/capture", httpx.Response(401, json={"error": "invalid_token", "access_token": "token-bbb"}))
    caplog.set_level(logging.INFO, logger="app.paypal")
    client = _client(endpoint)
    try:
        result = client.capture_order("ORDER-1")
    finally:
        client.close()
    assert result.error_code == PAYPAL_FAILED
    assert result.confirmation == UNCONFIRMED
    assert result.message == "PayPal rejected the access token."
    assert len(_money_posts(endpoint)) == 2
    rendered = "\n".join(record.getMessage() for record in caplog.records)
    _assert_secrets_absent(rendered, "token-aaa", "token-bbb", SECRET)


@pytest.mark.parametrize("refresh_status", [401, 400])
def test_failed_token_refresh_is_an_explicit_paypal_failure(refresh_status: int) -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token("token-aaa"))
    endpoint.push("/capture", httpx.Response(401, json={"error": "invalid_token"}))
    endpoint.push(
        "/v1/oauth2/token",
        httpx.Response(refresh_status, json={"error": "invalid_client", "error_description": SECRET}),
    )
    client = _client(endpoint)
    try:
        result = client.capture_order("ORDER-1")
    finally:
        client.close()
    assert result.error_code == PAYPAL_FAILED
    assert result.confirmation == UNCONFIRMED
    assert result.message == "PayPal rejected the Sandbox credentials."
    assert SECRET not in result.message
    assert len(_money_posts(endpoint)) == 1


def test_unclear_token_refresh_needs_checking() -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token("token-aaa"))
    endpoint.push("/capture", httpx.Response(401, json={"error": "invalid_token"}))
    endpoint.push("/v1/oauth2/token", httpx.Response(503, json={"access_token": TOKEN}))
    client = _client(endpoint)
    try:
        result = client.capture_order("ORDER-1")
    finally:
        client.close()
    assert result.error_code == NEEDS_CHECKING
    assert result.status == NEEDS_CHECKING
    assert result.confirmation == UNCONFIRMED
    assert TOKEN not in result.message
    assert len(_money_posts(endpoint)) == 1


def test_capture_body_maps_known_status_amount_and_ids() -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token())
    endpoint.push("/capture", httpx.Response(201, json=CAPTURED))
    client = _client(endpoint)
    try:
        result = client.capture_order("ORDER-1")
    finally:
        client.close()
    assert result.status == "completed"
    assert result.confirmation == "confirmed"
    assert result.paypal_status == "COMPLETED"
    assert result.paypal_order_id == "ORDER-1"
    assert result.paypal_capture_id == "CAP-1"
    assert result.amount_minor == 2500
    assert result.currency == "USD"


def test_unknown_capture_status_is_unconfirmed() -> None:
    body = {
        "id": "ORDER-9",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-9",
                            "status": "FROBNICATED",
                            "amount": {"currency_code": "USD", "value": "25.00"},
                        }
                    ]
                }
            }
        ],
    }
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token())
    endpoint.push("/capture", httpx.Response(201, json=body))
    client = _client(endpoint)
    try:
        result = client.capture_order("ORDER-9")
    finally:
        client.close()
    assert result.status == NEEDS_CHECKING
    assert result.confirmation == UNCONFIRMED
    assert result.error_code == NEEDS_CHECKING
    assert result.paypal_status == "FROBNICATED"
    assert result.paypal_order_id == "ORDER-9"
    assert result.paypal_capture_id == "CAP-9"


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(
            500,
            json={
                "id": "ORDER-1",
                "status": "COMPLETED",
                "purchase_units": CAPTURED["purchase_units"],
            },
        ),
        httpx.ReadTimeout("timed out"),
    ],
)
def test_timeout_or_http_500_does_not_repeat_a_capture(failure: httpx.Response | Exception) -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token())
    endpoint.push("/capture", failure)
    client = _client(endpoint)
    try:
        result = client.capture_order("ORDER-1")
    finally:
        client.close()
    assert result.status == NEEDS_CHECKING
    assert result.confirmation == UNCONFIRMED
    assert result.error_code == NEEDS_CHECKING
    assert result.paypal_status is None
    assert result.paypal_capture_id is None
    assert result.paypal_order_id == "ORDER-1"
    if isinstance(failure, httpx.Response):
        assert result.http_status == 500
    else:
        assert result.http_status is None
    assert len(_money_posts(endpoint)) == 1


def test_http_500_does_not_repeat_a_refund() -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token())
    endpoint.push("/refund", httpx.Response(500, json={"id": "REFUND-1", "status": "COMPLETED"}))
    client = _client(endpoint)
    try:
        result = client.refund_capture("CAP-1", 2500, "USD", "refund-request-1")
    finally:
        client.close()
    assert result.status == NEEDS_CHECKING
    assert result.confirmation == UNCONFIRMED
    assert result.paypal_status is None
    assert result.paypal_refund_id is None
    assert len(_money_posts(endpoint)) == 1
    refund = _money_posts(endpoint)[0]
    assert refund.headers["paypal-request-id"] == "refund-request-1"
    assert json.loads(refund.content)["amount"] == {"currency_code": "USD", "value": "25.00"}


def test_explicit_paypal_failure_is_not_retried_and_scrubs_the_secret() -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token())
    endpoint.push(
        "/capture",
        httpx.Response(
            422,
            json={
                "name": "UNPROCESSABLE_ENTITY",
                "message": "The requested action could not be performed.",
                "details": [{"issue": "INSTRUMENT_DECLINED", "description": f"declined {SECRET}"}],
            },
        ),
    )
    client = _client(endpoint)
    try:
        result = client.capture_order("ORDER-1")
    finally:
        client.close()
    assert result.error_code == PAYPAL_FAILED
    assert result.status == "failed"
    assert result.confirmation == UNCONFIRMED
    assert result.issue == "INSTRUMENT_DECLINED"
    assert SECRET not in result.message
    assert "[redacted]" in result.message
    assert len(_money_posts(endpoint)) == 1


def test_payer_still_required_stays_awaiting_payer() -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token())
    endpoint.push(
        "/capture",
        httpx.Response(
            422,
            json={
                "name": "UNPROCESSABLE_ENTITY",
                "details": [
                    {
                        "issue": "ORDER_NOT_APPROVED",
                        "description": "Payer has not yet approved the Order for payment.",
                    }
                ],
            },
        ),
    )
    client = _client(endpoint)
    try:
        result = client.capture_order("ORDER-1")
    finally:
        client.close()
    assert result.status == "awaiting_payer"
    assert result.confirmation == UNCONFIRMED
    assert result.error_code is None
    assert result.issue == "ORDER_NOT_APPROVED"
    assert result.paypal_order_id == "ORDER-1"
    assert result.paypal_capture_id is None
    assert len(_money_posts(endpoint)) == 1


def test_already_captured_is_unclear_and_is_not_sent_again() -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token())
    endpoint.push(
        "/capture",
        httpx.Response(
            422,
            json={
                "name": "UNPROCESSABLE_ENTITY",
                "details": [{"issue": "ORDER_ALREADY_CAPTURED", "description": "Order already captured."}],
            },
        ),
    )
    client = _client(endpoint)
    try:
        result = client.capture_order("ORDER-1")
    finally:
        client.close()
    assert result.status == NEEDS_CHECKING
    assert result.confirmation == UNCONFIRMED
    assert result.error_code == NEEDS_CHECKING
    assert len(_money_posts(endpoint)) == 1


def test_refund_and_read_parse_a_recognized_body() -> None:
    endpoint = Endpoint()
    endpoint.push("/v1/oauth2/token", _token())
    endpoint.push(
        "/refund",
        httpx.Response(
            201,
            json={"id": "REFUND-1", "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "25.00"}},
        ),
    )
    endpoint.push(
        "/v2/payments/captures/CAP-1",
        httpx.Response(
            200,
            json={
                "id": "CAP-1",
                "status": "REFUNDED",
                "amount": {"currency_code": "USD", "value": "25.00"},
                "supplementary_data": {"related_ids": {"order_id": "ORDER-1"}},
            },
        ),
    )
    client = _client(endpoint)
    try:
        refund = client.refund_capture("CAP-1", 2500, "USD", "refund-request-1")
        read = client.get_order_or_capture(paypal_capture_id="CAP-1")
    finally:
        client.close()
    assert refund.status == "completed"
    assert refund.confirmation == "confirmed"
    assert refund.paypal_refund_id == "REFUND-1"
    assert refund.amount_minor == 2500
    assert read.status == "refunded"
    assert read.confirmation == "confirmed"
    assert read.paypal_capture_id == "CAP-1"
    assert read.paypal_order_id == "ORDER-1"
    assert len([request for request in endpoint.seen if request.url.path == "/v1/oauth2/token"]) == 1


def test_fake_adapter_matches_the_interface_and_records_scripted_results() -> None:
    fake = FakePayPalAdapter()
    assert isinstance(fake, PayPalAdapter)
    fake.queue(
        "capture_order",
        PayPalCall(
            operation="capture_order",
            status="completed",
            confirmation="confirmed",
            paypal_status="COMPLETED",
            paypal_order_id="ORDER-1",
            paypal_capture_id="CAP-1",
        ),
    )
    fake.queue(
        "capture_order",
        PayPalCall(
            operation="capture_order",
            status=NEEDS_CHECKING,
            confirmation=UNCONFIRMED,
            paypal_status="FROBNICATED",
            error_code=NEEDS_CHECKING,
        ),
    )
    known = fake.capture_order("ORDER-1")
    unknown = fake.capture_order("ORDER-1")
    assert known.status == "completed"
    assert known.confirmation == "confirmed"
    assert unknown.status == NEEDS_CHECKING
    assert unknown.confirmation == UNCONFIRMED
    assert [call["operation"] for call in fake.calls] == ["capture_order", "capture_order"]
    created = fake.create_order(2500, "USD", RETURN_URL, CANCEL_URL)
    assert created.amount_minor == 2500
    assert created.currency == "USD"
    assert created.status == "awaiting_payer"


def test_live_client_matches_the_adapter_interface() -> None:
    client = _client(Endpoint())
    try:
        assert isinstance(client, PayPalAdapter)
    finally:
        client.close()


def test_only_the_paypal_module_imports_an_http_client() -> None:
    http_import = re.compile(r"(?m)^(?:from|import)\s+(?:httpx|requests|urllib|http\.client|aiohttp)\b")
    host = re.compile(r"api(?:-m)?(?:\.sandbox)?\.paypal\.com")
    offenders: list[str] = []
    api_root = ROOT / "apps" / "api" / "app"
    for path in api_root.rglob("*.py"):
        if "paypal" in path.parts:
            continue
        text_value = path.read_text(encoding="utf-8")
        if http_import.search(text_value) or host.search(text_value):
            offenders.append(str(path.relative_to(ROOT)))
    web_root = ROOT / "apps" / "web"
    for path in web_root.rglob("*"):
        if not path.is_file():
            continue
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        if path.suffix not in {".ts", ".tsx", ".js", ".mjs", ".css"}:
            continue
        text_value = path.read_text(encoding="utf-8", errors="ignore")
        if host.search(text_value) or "httpx" in text_value:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_client_secret_is_read_by_the_api_and_not_by_other_modules() -> None:
    allowed = {
        ROOT / "apps" / "api" / "app" / "core" / "config.py",
        ROOT / "apps" / "api" / "app" / "modules" / "paypal" / "sandbox_check.py",
    }
    offenders: list[str] = []
    for path in (ROOT / "apps" / "api" / "app").rglob("*.py"):
        if path in allowed:
            continue
        if "PAYPAL_CLIENT_SECRET" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
    assert "PAYPAL_CLIENT_SECRET" in (ROOT / "apps" / "api" / "app" / "core" / "config.py").read_text(encoding="utf-8")


def test_paypal_module_does_not_touch_the_database() -> None:
    paypal_dir = ROOT / "apps" / "api" / "app" / "modules" / "paypal"
    for path in paypal_dir.rglob("*.py"):
        text_value = path.read_text(encoding="utf-8")
        assert "sqlalchemy" not in text_value
        assert "get_session" not in text_value


def test_sandbox_check_skips_when_credentials_are_absent(capsys: pytest.CaptureFixture[str]) -> None:
    assert credentials_present({"PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": "", "PAYPAL_API_BASE": ""}) is False
    assert (
        credentials_present(
            {
                "PAYPAL_CLIENT_ID": "test-client-id",
                "PAYPAL_CLIENT_SECRET": SECRET,
                "PAYPAL_API_BASE": "https://api-m.sandbox.paypal.com",
            }
        )
        is False
    )
    assert fetch_token_status({"PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": "", "PAYPAL_API_BASE": ""}) is None
    assert main() == 0
    assert capsys.readouterr().out.strip() == "skipped"


@pytest.mark.skipif(not credentials_present(), reason="PayPal Sandbox credentials are absent")
def test_sandbox_token_prints_only_the_http_status(capsys: pytest.CaptureFixture[str]) -> None:
    status = fetch_token_status()
    assert isinstance(status, int)
    assert main() == 0
    printed = capsys.readouterr().out.strip().splitlines()
    assert printed == [str(status)]
    assert SECRET not in "\n".join(printed)
