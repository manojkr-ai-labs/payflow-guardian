from __future__ import annotations

import logging

from app.core.redaction import redact_text, redact_value


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, dict):
            record.args = redact_value(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_value(item) for item in record.args)
        if not isinstance(record.msg, str):
            record.msg = redact_value(record.msg)
        elif not record.args:
            record.msg = redact_text(record.msg)

        original_get_message = record.getMessage

        def get_message() -> str:
            return redact_text(original_get_message())

        record.getMessage = get_message  # type: ignore[method-assign]
        return True


def install_log_filter() -> None:
    redactor = SecretRedactionFilter()
    logging.getLogger().addFilter(redactor)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "app"):
        logging.getLogger(name).addFilter(redactor)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "secrets": {"()": "app.core.logging.SecretRedactionFilter"},
    },
    "formatters": {
        "default": {"format": "%(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["secrets"],
            "stream": "ext://sys.stdout",
        },
    },
    "root": {"handlers": ["default"], "level": "INFO"},
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
}
