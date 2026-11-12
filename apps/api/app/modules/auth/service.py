from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import cookie_secure
from app.core.errors import AppError, unauthorized
from app.modules.auth.models import AuthSession, Membership, User

COOKIE_NAME = "pf_session"
SESSION_HOURS = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def hash_session_token(token: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def user_payload(membership: Membership) -> dict[str, str]:
    return {
        "id": str(membership.user.id),
        "email": membership.user.email,
        "display_name": membership.user.display_name,
        "role": membership.role,
        "merchant_id": str(membership.merchant_id),
        "merchant_name": membership.merchant.name,
    }


def authenticate(db: Session, email: str, password: str) -> Membership:
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None or not verify_password(password, user.password_hash):
        raise unauthorized("The email or password is not correct.")
    membership = db.scalar(
        select(Membership)
        .options(joinedload(Membership.user), joinedload(Membership.merchant))
        .where(Membership.user_id == user.id)
    )
    if membership is None:
        raise unauthorized("The email or password is not correct.")
    return membership


def start_session(db: Session, membership: Membership, secret: str) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=hash_session_token(token, secret),
            user_id=membership.user_id,
            merchant_id=membership.merchant_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS),
        )
    )
    db.flush()
    return token


def membership_for_token(db: Session, token: str, secret: str) -> Membership:
    if not token:
        raise unauthorized()
    token_hash = hash_session_token(token, secret)
    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
    if auth_session is None:
        raise unauthorized()
    if _as_utc(auth_session.expires_at) <= datetime.now(timezone.utc):
        db.delete(auth_session)
        db.flush()
        raise unauthorized("Sign in again.")
    membership = db.scalar(
        select(Membership)
        .options(joinedload(Membership.user), joinedload(Membership.merchant))
        .where(
            Membership.user_id == auth_session.user_id,
            Membership.merchant_id == auth_session.merchant_id,
        )
    )
    if membership is None:
        raise unauthorized()
    return membership


def end_session(db: Session, token: str, secret: str) -> None:
    if not token:
        return
    token_hash = hash_session_token(token, secret)
    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
    if auth_session is not None:
        db.delete(auth_session)
        db.flush()


def require_owner(membership: Membership) -> None:
    if membership.role != "owner":
        raise AppError("forbidden", "Only an owner can approve a refund.", 403)


def session_cookie_kwargs(web_origin: str) -> dict[str, object]:
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": cookie_secure(web_origin),
        "path": "/",
        "max_age": SESSION_HOURS * 60 * 60,
    }
