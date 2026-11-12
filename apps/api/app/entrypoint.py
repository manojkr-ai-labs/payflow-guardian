from __future__ import annotations

import sys

import uvicorn

from app.core.config import SettingsError, load_settings
from app.core.logging import LOGGING_CONFIG


def main() -> None:
    try:
        load_settings()
    except SettingsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    from alembic.config import main as alembic_main

    alembic_main(argv=["upgrade", "head"])
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_config=LOGGING_CONFIG)


if __name__ == "__main__":
    main()
