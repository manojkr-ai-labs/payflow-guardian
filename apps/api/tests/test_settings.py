import pytest

from app.core.config import REQUIRED_SETTINGS, SettingsError, cookie_secure, load_settings


def valid_source() -> dict[str, str]:
    return {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "SESSION_SECRET": "test-session-secret",
        "PAYPAL_CLIENT_ID": "test-client-id",
        "PAYPAL_CLIENT_SECRET": "test-client-secret",
        "PAYPAL_API_BASE": "https://api-m.sandbox.paypal.com",
        "WEB_ORIGIN": "http://localhost:3000",
    }


def test_missing_database_url_names_the_setting() -> None:
    source = valid_source()
    source["DATABASE_URL"] = "  "
    with pytest.raises(SettingsError, match="DATABASE_URL"):
        load_settings(source)


def test_missing_paypal_client_secret_names_the_setting() -> None:
    source = valid_source()
    del source["PAYPAL_CLIENT_SECRET"]
    with pytest.raises(SettingsError, match="PAYPAL_CLIENT_SECRET"):
        load_settings(source)


def test_webhook_and_ai_settings_may_be_empty() -> None:
    settings = load_settings(valid_source())
    assert settings.paypal_webhook_id == ""
    assert settings.ai_api_key == ""
    assert settings.ai_model == ""


def test_required_setting_names() -> None:
    assert "PAYPAL_WEBHOOK_ID" not in REQUIRED_SETTINGS
    assert "AI_API_KEY" not in REQUIRED_SETTINGS


def test_cookie_is_secure_only_for_https() -> None:
    assert cookie_secure("https://payflow.example") is True
    assert cookie_secure("http://localhost:3000") is False
