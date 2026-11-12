"""Fetch a Sandbox access token and print only the HTTP status.

Run from apps/api:

    python -m app.modules.paypal.sandbox_check

When PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, or PAYPAL_API_BASE is absent, or the
values are the local test placeholders, the command prints ``skipped`` and does
not call PayPal. A real call prints the status code and nothing else.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

import httpx

_PLACEHOLDER_IDS = frozenset({"", "test-client-id"})
_PLACEHOLDER_SECRETS = frozenset({"", "test-client-secret"})


def credentials_present(source: Mapping[str, str] | None = None) -> bool:
    values = os.environ if source is None else source
    client_id = values.get("PAYPAL_CLIENT_ID", "").strip()
    secret = values.get("PAYPAL_CLIENT_SECRET", "").strip()
    base = values.get("PAYPAL_API_BASE", "").strip()
    if client_id in _PLACEHOLDER_IDS or secret in _PLACEHOLDER_SECRETS or not base:
        return False
    return True


def fetch_token_status(source: Mapping[str, str] | None = None) -> int | None:
    """Return the token endpoint HTTP status, or None when credentials are absent."""
    values = os.environ if source is None else source
    if not credentials_present(values):
        return None
    base = values["PAYPAL_API_BASE"].strip().rstrip("/")
    with httpx.Client(base_url=base, timeout=httpx.Timeout(20.0), follow_redirects=False) as client:
        response = client.post(
            "/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(values["PAYPAL_CLIENT_ID"].strip(), values["PAYPAL_CLIENT_SECRET"].strip()),
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
        )
    return response.status_code


def main() -> int:
    if not credentials_present():
        print("skipped")
        return 0
    try:
        status = fetch_token_status()
    except httpx.HTTPError:
        print("PayPal did not answer.", file=sys.stderr)
        return 1
    if status is None:
        print("skipped")
        return 0
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
