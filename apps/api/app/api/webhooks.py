from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db, get_settings
from app.modules.webhooks.service import apply_webhook

router = APIRouter(prefix="/webhooks")


@router.post("/paypal")
async def paypal_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    settings = get_settings()
    apply_webhook(
        db,
        body=await request.body(),
        headers=dict(request.headers),
        webhook_id=settings.paypal_webhook_id,
    )
    return {"received": True}
