"""Webhook signature check. This function does not call PayPal."""

from __future__ import annotations

from collections.abc import Mapping


def verify_webhook(*, body: bytes, headers: Mapping[str, str], webhook_id: str) -> bool:
    """Return whether this body is a verified PayPal webhook.

    An empty PAYPAL_WEBHOOK_ID is never verified. Tests replace this function
    instead of calling PayPal.
    """
    del body, headers
    return bool(webhook_id.strip()) and False
