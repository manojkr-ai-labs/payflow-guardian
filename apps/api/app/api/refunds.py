import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_paypal
from app.core.db import get_db
from app.modules.auth.models import Membership
from app.modules.auth.service import require_owner
from app.modules.paypal.types import PayPalAdapter
from app.modules.refunds.service import (
    approve_refund,
    get_refund,
    list_refunds,
    prepare_refund,
    refund_payload,
    reject_refund,
)

router = APIRouter(prefix="/refunds")


class PrepareRefundBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    payment_id: uuid.UUID
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    reason: str = Field(min_length=1, max_length=500)


@router.post("")
def create_refund(
    body: PrepareRefundBody,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> JSONResponse:
    outcome = prepare_refund(
        db,
        merchant_id=membership.merchant_id,
        user_id=membership.user_id,
        payment_id=body.payment_id,
        amount_minor=body.amount_minor,
        currency=body.currency,
        reason=body.reason,
    )
    return JSONResponse(
        status_code=201 if outcome.created else 200,
        content={"refund": refund_payload(outcome.refund)},
    )


@router.get("")
def read_refunds(
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    refunds = list_refunds(db, membership.merchant_id)
    return {"refunds": [refund_payload(refund) for refund in refunds]}


@router.post("/{refund_id}/approve")
def approve_refund_route(
    refund_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    paypal: PayPalAdapter = Depends(get_paypal),
) -> JSONResponse:
    require_owner(membership)
    outcome = approve_refund(
        db,
        merchant_id=membership.merchant_id,
        user_id=membership.user_id,
        refund_id=refund_id,
        paypal=paypal,
    )
    payload = refund_payload(outcome.refund)
    if outcome.error is not None:
        return JSONResponse(
            status_code=outcome.error.status_code,
            content={"error": {"code": outcome.error.code, "message": outcome.error.message}, "refund": payload},
        )
    return JSONResponse(status_code=200, content={"refund": payload})


@router.post("/{refund_id}/reject")
def reject_refund_route(
    refund_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    require_owner(membership)
    refund = reject_refund(
        db,
        merchant_id=membership.merchant_id,
        user_id=membership.user_id,
        refund_id=refund_id,
    )
    return {"refund": refund_payload(refund)}


@router.get("/{refund_id}")
def read_refund(
    refund_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    refund = get_refund(db, membership.merchant_id, refund_id)
    return {"refund": refund_payload(refund)}
