from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership
from app.core.db import get_db, get_settings
from app.modules.auth.models import Membership
from app.modules.auth.service import (
    COOKIE_NAME,
    authenticate,
    end_session,
    session_cookie_kwargs,
    start_session,
    user_payload,
)

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


def _clear_cookie(response: Response) -> None:
    settings = get_settings()
    kwargs = session_cookie_kwargs(settings.web_origin)
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=bool(kwargs["secure"]),
    )


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict[str, dict[str, str]]:
    settings = get_settings()
    membership = authenticate(db, body.email, body.password)
    token = start_session(db, membership, settings.session_secret)
    response.set_cookie(value=token, **session_cookie_kwargs(settings.web_origin))
    return {"user": user_payload(membership)}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    settings = get_settings()
    end_session(db, request.cookies.get(COOKIE_NAME, ""), settings.session_secret)
    _clear_cookie(response)


@router.get("/me")
def me(membership: Membership = Depends(get_current_membership)) -> dict[str, dict[str, str]]:
    return {"user": user_payload(membership)}
