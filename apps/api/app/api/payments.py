import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_paypal
from app.core.db import get_db, get_settings
from app.modules.auth.models import Membership
from app.modules.payments.service import (
    capture_payment,
    create_test_payment,
    get_payment,
    investigate_payment,
    list_payments,
    payment_list_item,
    payment_payload,
)
from app.modules.paypal.types import PayPalAdapter

router = APIRouter(prefix="/payments")


class CreatePaymentBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    test_order_code: str = Field(min_length=1, max_length=32)


@router.post("")
def create_payment(
    body: CreatePaymentBody,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    paypal: PayPalAdapter = Depends(get_paypal),
) -> JSONResponse:
    settings = get_settings()
    outcome = create_test_payment(
        db,
        merchant_id=membership.merchant_id,
        user_id=membership.user_id,
        test_order_code=body.test_order_code,
        idempotency_key=idempotency_key,
        paypal=paypal,
        web_origin=settings.web_origin,
    )
    payload = payment_payload(outcome.payment)
    if outcome.error is not None:
        return JSONResponse(
            status_code=outcome.error.status_code,
            content={
                "error": {"code": outcome.error.code, "message": outcome.error.message},
                "payment": payload,
            },
        )
    return JSONResponse(status_code=201 if outcome.inserted else 200, content={"payment": payload})


@router.get("")
def read_payments(
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    q: str | None = None,
    status: str | None = None,
) -> dict[str, object]:
    payments = list_payments(db, membership.merchant_id, q=q, status=status)
    return {"payments": [payment_list_item(payment) for payment in payments]}


@router.get("/{payment_id}")
def read_payment(
    payment_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    payment = get_payment(db, membership.merchant_id, payment_id)
    return {"payment": payment_payload(payment)}


@router.post("/{payment_id}/capture")
def capture_payment_route(
    payment_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    paypal: PayPalAdapter = Depends(get_paypal),
) -> JSONResponse:
    outcome = capture_payment(
        db,
        merchant_id=membership.merchant_id,
        user_id=membership.user_id,
        payment_id=payment_id,
        paypal=paypal,
    )
    payload = payment_payload(outcome.payment)
    if outcome.error is not None:
        return JSONResponse(
            status_code=outcome.error.status_code,
            content={
                "error": {"code": outcome.error.code, "message": outcome.error.message},
                "payment": payload,
            },
        )
    return JSONResponse(status_code=200, content={"payment": payload})


@router.post("/{payment_id}/investigate")
def investigate_payment_route(
    payment_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    paypal: PayPalAdapter = Depends(get_paypal),
) -> dict[str, object]:
    payment = investigate_payment(
        db,
        merchant_id=membership.merchant_id,
        user_id=membership.user_id,
        payment_id=payment_id,
        paypal=paypal,
    )
    return {"payment": payment_payload(payment)}
