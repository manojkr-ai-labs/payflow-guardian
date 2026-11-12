"""The only module that speaks to PayPal."""

from app.modules.paypal.client import PayPalClient, get_paypal_client
from app.modules.paypal.fake import FakePayPalAdapter
from app.modules.paypal.status import map_paypal_status
from app.modules.paypal.types import PayPalAdapter, PayPalCall

__all__ = [
    "FakePayPalAdapter",
    "PayPalAdapter",
    "PayPalCall",
    "PayPalClient",
    "get_paypal_client",
    "map_paypal_status",
]
