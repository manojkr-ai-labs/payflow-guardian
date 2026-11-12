"""Server-defined test orders. Amount and currency are read here, never from the client."""

from app.modules.catalog.orders import TEST_ORDERS, TestOrder, get_test_order, list_test_orders

__all__ = ["TEST_ORDERS", "TestOrder", "get_test_order", "list_test_orders"]
