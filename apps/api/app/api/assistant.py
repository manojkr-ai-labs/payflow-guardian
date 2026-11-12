from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_paypal
from app.core.db import get_db, get_settings
from app.modules.assistant.service import Model, default_model, handle_message
from app.modules.auth.models import Membership
from app.modules.paypal.types import PayPalAdapter

router = APIRouter(prefix="/assistant")


class MessageBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str = Field(min_length=1, max_length=64)


def get_model() -> Model:
    return default_model


@router.post("/messages")
def post_message(
    body: MessageBody,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    paypal: PayPalAdapter = Depends(get_paypal),
    model: Model = Depends(get_model),
) -> dict[str, object]:
    settings = get_settings()
    return handle_message(
        db,
        merchant_id=membership.merchant_id,
        user_id=membership.user_id,
        message=body.message,
        conversation_id=body.conversation_id,
        paypal=paypal,
        web_origin=settings.web_origin,
        model=model,
    )
