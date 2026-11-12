import logging

from app.core.logging import SecretRedactionFilter
from app.core.redaction import redact_value


def test_log_filter_removes_bearer_token_and_client_secret() -> None:
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='Authorization: Bearer fake-bearer-token {"client_secret": "fake-client-secret", "paypal_id": "ORDER-1"}',
        args=(),
        exc_info=None,
    )
    assert SecretRedactionFilter().filter(record) is True
    rendered = record.getMessage()
    assert "fake-bearer-token" not in rendered
    assert "fake-client-secret" not in rendered
    assert "ORDER-1" in rendered
    assert "[redacted]" in rendered


def test_filter_redacts_formatted_bearer_token_without_dropping_args() -> None:
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Authorization: Bearer %s",
        args=("fake-bearer-token",),
        exc_info=None,
    )
    assert SecretRedactionFilter().filter(record) is True
    assert record.args == ("fake-bearer-token",)
    assert "fake-bearer-token" not in record.getMessage()


def test_filter_preserves_uvicorn_access_args() -> None:
    args = ("127.0.0.1:1", "GET", "/api/health", "1.1", 200)
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=args,
        exc_info=None,
    )
    assert SecretRedactionFilter().filter(record) is True
    assert record.args == args


def test_mapping_redacts_password_and_access_token() -> None:
    cleaned = redact_value(
        {
            "password": "owner-test-example",
            "access_token": "token-value",
            "paypal_id": "ORDER-1",
            "nested": {"api_key": "key-value", "status": "CREATED"},
        }
    )
    assert cleaned["password"] == "[redacted]"
    assert cleaned["access_token"] == "[redacted]"
    assert cleaned["nested"]["api_key"] == "[redacted]"
    assert cleaned["paypal_id"] == "ORDER-1"
    assert cleaned["nested"]["status"] == "CREATED"
    assert "owner-test-example" not in str(cleaned)
    assert "token-value" not in str(cleaned)
    assert "key-value" not in str(cleaned)
