from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SECRET_FIELD_NAMES = frozenset(
    {"authorization", "client_secret", "api_key", "password", "access_token"}
)
REDACTED = "[redacted]"

_ASSIGNMENT = re.compile(
    r"(?i)((?:authorization|client_secret|api_key|password|access_token)\"?\s*[:=]\s*\"?(?:bearer\s+)?)"
    r"([^\"\s,}&]+)"
)


def redact_text(value: str) -> str:
    return _ASSIGNMENT.sub(lambda match: match.group(1) + REDACTED, value)


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        cleaned: dict[Any, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_FIELD_NAMES:
                cleaned[key] = REDACTED
            else:
                cleaned[key] = redact_value(item)
        return cleaned
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    return value
