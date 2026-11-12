from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Membership, Merchant, User
from app.modules.auth.service import hash_password

DEMO_MERCHANT_NAME = "PayFlow Demo Shop"
DEMO_ACCOUNTS = (
    {
        "email": "owner@payflow.test",
        "display_name": "Demo Owner",
        "password": "owner-test-example",
        "role": "owner",
    },
    {
        "email": "support@payflow.test",
        "display_name": "Demo Support",
        "password": "support-test-example",
        "role": "support",
    },
)


def seed_demo(db: Session) -> Merchant:
    merchant = db.scalar(select(Merchant).where(Merchant.name == DEMO_MERCHANT_NAME))
    if merchant is None:
        merchant = Merchant(name=DEMO_MERCHANT_NAME)
        db.add(merchant)
        db.flush()

    for account in DEMO_ACCOUNTS:
        user = db.scalar(select(User).where(User.email == account["email"]))
        if user is None:
            user = User(
                email=account["email"],
                display_name=account["display_name"],
                password_hash=hash_password(account["password"]),
            )
            db.add(user)
            db.flush()
        membership = db.scalar(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.merchant_id == merchant.id,
            )
        )
        if membership is None:
            db.add(
                Membership(
                    user_id=user.id,
                    merchant_id=merchant.id,
                    role=account["role"],
                )
            )
    db.flush()
    return merchant
