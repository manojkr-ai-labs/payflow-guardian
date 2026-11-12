from fastapi import APIRouter

from app.api.activity import router as activity_router
from app.api.assistant import router as assistant_router
from app.api.auth import router as auth_router
from app.api.catalog import router as catalog_router
from app.api.health import router as health_router
from app.api.payments import router as payments_router
from app.api.refunds import router as refunds_router
from app.api.webhooks import router as webhooks_router

router = APIRouter(prefix="/api")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(catalog_router)
router.include_router(payments_router)
router.include_router(activity_router)
router.include_router(refunds_router)
router.include_router(webhooks_router)
router.include_router(assistant_router)
