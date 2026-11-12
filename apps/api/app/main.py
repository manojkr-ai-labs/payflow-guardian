from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.router import router
from app.core.db import get_session_factory, get_settings
from app.core.errors import AppError
from app.core.logging import install_log_filter
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.activity import models as activity_models  # noqa: F401
from app.modules.payments import models as payment_models  # noqa: F401
from app.modules.assistant import models as assistant_models  # noqa: F401
from app.modules.refunds import models as refund_models  # noqa: F401
from app.modules.webhooks import models as webhook_models  # noqa: F401
from app.modules.auth.seed import seed_demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    install_log_filter()
    settings = get_settings()
    if not settings.skip_seed:
        db = get_session_factory()()
        try:
            seed_demo(db)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="PayFlow Guardian", lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(AppError)
    def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    def handle_validation(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_failed", "message": "The request is missing a required field."}},
        )

    return app


app = create_app()
