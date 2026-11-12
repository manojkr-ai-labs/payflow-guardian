from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db, get_settings
from app.modules.auth.models import Membership
from app.modules.auth.service import COOKIE_NAME, membership_for_token
from app.modules.paypal.client import get_paypal_client
from app.modules.paypal.types import PayPalAdapter


def get_paypal() -> PayPalAdapter:
    return get_paypal_client()


def get_current_membership(request: Request, db: Session = Depends(get_db)) -> Membership:
    settings = get_settings()
    token = request.cookies.get(COOKIE_NAME, "")
    return membership_for_token(db, token, settings.session_secret)
