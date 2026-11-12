"""Create a catalog Sandbox order and print the approval link.

Run from apps/api:

    python -m app.modules.payments.sandbox_check

When PayPal credentials are absent or still the local placeholders, the command
prints ``skipped`` and does not call PayPal. A real call prints the HTTP status,
the catalog amount, and the approval link. It does not print the access token.
"""

from __future__ import annotations

import sys

from app.core.config import load_settings
from app.modules.catalog.orders import get_test_order
from app.modules.paypal.client import PayPalClient
from app.modules.paypal.sandbox_check import credentials_present
from app.modules.paypal.types import PayPalCall


def create_demo_order() -> PayPalCall | None:
    """Create DEMO-25 when credentials exist. Returns None without calling PayPal."""
    if not credentials_present():
        return None
    item = get_test_order("DEMO-25")
    if item is None:
        raise RuntimeError("DEMO-25 is missing from the catalog")
    settings = load_settings()
    origin = settings.web_origin.strip().rstrip("/")
    client = PayPalClient(settings)
    try:
        return client.create_order(
            item.amount_minor,
            item.currency,
            f"{origin}/payments/sandbox-check/return",
            f"{origin}/payments/sandbox-check/cancel",
        )
    finally:
        client.close()


def main() -> int:
    if not credentials_present():
        print("skipped")
        return 0
    item = get_test_order("DEMO-25")
    if item is None:
        print("DEMO-25 is missing from the catalog.", file=sys.stderr)
        return 1
    try:
        result = create_demo_order()
    except Exception:
        print("PayPal did not answer.", file=sys.stderr)
        return 1
    if result is None:
        print("skipped")
        return 0
    print(result.http_status if result.http_status is not None else "none")
    print(f"{item.display_amount} {item.currency}")
    amount_matches = result.amount_minor in (None, item.amount_minor) and (
        result.currency is None or result.currency.upper() == item.currency
    )
    if result.approve_url and result.paypal_order_id and amount_matches and result.error_code is None:
        print(result.approve_url)
        return 0
    print(result.error_code or result.status)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
