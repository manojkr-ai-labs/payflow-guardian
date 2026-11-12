from __future__ import annotations

from dataclasses import dataclass

from app.modules.paypal.money import minor_to_paypal


@dataclass(frozen=True, slots=True)
class TestOrder:
    code: str
    description: str
    amount_minor: int
    currency: str

    @property
    def display_amount(self) -> str:
        return minor_to_paypal(self.amount_minor, self.currency)


TEST_ORDERS: tuple[TestOrder, ...] = (
    TestOrder("DEMO-25", "Demo consultation", 2500, "USD"),
    TestOrder("DEMO-49", "Demo product", 4900, "USD"),
)

_BY_CODE = {item.code: item for item in TEST_ORDERS}


def list_test_orders() -> tuple[TestOrder, ...]:
    return TEST_ORDERS


def get_test_order(code: str | None) -> TestOrder | None:
    if not isinstance(code, str):
        return None
    return _BY_CODE.get(code.strip().upper())
