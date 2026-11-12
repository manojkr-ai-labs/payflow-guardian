from __future__ import annotations

# PayPal currencies that use zero decimal places.
_ZERO_DECIMAL = frozenset({"HUF", "JPY", "TWD"})


def require_money(amount_minor: int, currency: str) -> str:
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int) or amount_minor < 0:
        raise ValueError("amount_minor must be a non-negative integer")
    code = currency.strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError("currency must be a 3-letter code")
    return code


def minor_to_paypal(amount_minor: int, currency: str) -> str:
    code = require_money(amount_minor, currency)
    if code in _ZERO_DECIMAL:
        return str(amount_minor)
    whole, cents = divmod(amount_minor, 100)
    return f"{whole}.{cents:02d}"


def paypal_to_minor(value: object, currency: str) -> int | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    code = currency.strip().upper()
    if len(code) != 3:
        return None
    if code in _ZERO_DECIMAL:
        if text.startswith("-") or not text.isdigit():
            return None
        return int(text)
    if "." not in text:
        if text.startswith("-") or not text.isdigit():
            return None
        return int(text) * 100
    whole, frac = text.split(".", 1)
    if whole.startswith("-") or not whole.isdigit() or not frac.isdigit() or len(frac) > 2:
        return None
    return int(whole) * 100 + int(frac.ljust(2, "0"))
