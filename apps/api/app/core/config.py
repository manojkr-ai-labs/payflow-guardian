from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel

REQUIRED_SETTINGS = (
    "DATABASE_URL",
    "SESSION_SECRET",
    "PAYPAL_CLIENT_ID",
    "PAYPAL_CLIENT_SECRET",
    "PAYPAL_API_BASE",
    "WEB_ORIGIN",
)


class SettingsError(Exception):
    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("Missing required setting: " + ", ".join(missing))


class Settings(BaseModel):
    database_url: str
    session_secret: str
    paypal_client_id: str
    paypal_client_secret: str
    paypal_api_base: str
    web_origin: str
    paypal_webhook_id: str = ""
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    skip_seed: bool = False


def load_settings(source: Mapping[str, str] | None = None) -> Settings:
    values = dict(os.environ if source is None else source)
    missing = [name for name in REQUIRED_SETTINGS if not values.get(name, "").strip()]
    if missing:
        raise SettingsError(missing)
    return Settings(
        database_url=values["DATABASE_URL"].strip(),
        session_secret=values["SESSION_SECRET"].strip(),
        paypal_client_id=values["PAYPAL_CLIENT_ID"].strip(),
        paypal_client_secret=values["PAYPAL_CLIENT_SECRET"].strip(),
        paypal_api_base=values["PAYPAL_API_BASE"].strip(),
        web_origin=values["WEB_ORIGIN"].strip(),
        paypal_webhook_id=values.get("PAYPAL_WEBHOOK_ID", "").strip(),
        ai_base_url=values.get("AI_BASE_URL", "").strip(),
        ai_api_key=values.get("AI_API_KEY", "").strip(),
        ai_model=values.get("AI_MODEL", "").strip(),
        skip_seed=values.get("PAYFLOW_SKIP_SEED", "").strip() == "1",
    )


def cookie_secure(web_origin: str) -> bool:
    return web_origin.lower().startswith("https://")
