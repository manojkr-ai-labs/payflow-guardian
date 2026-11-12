from app.core.errors import AppError
from app.modules.auth.seed import DEMO_ACCOUNTS
from app.modules.auth.service import require_owner


def _account(role: str) -> dict[str, str]:
    return next(account for account in DEMO_ACCOUNTS if account["role"] == role)


def test_owner_and_support_can_log_in_and_out(client) -> None:
    for role in ("owner", "support"):
        account = _account(role)
        login = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
        assert login.status_code == 200
        body = login.json()["user"]
        assert body["role"] == role
        assert body["merchant_name"] == "PayFlow Demo Shop"
        assert "password" not in login.text
        cookie = login.headers["set-cookie"].lower()
        assert "pf_session=" in cookie
        assert "httponly" in cookie
        assert "samesite=lax" in cookie
        assert "secure" not in cookie

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["role"] == role

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 204
        assert client.get("/api/auth/me").status_code == 401


def test_wrong_password_is_unauthorized(client) -> None:
    account = _account("owner")
    response = client.post("/api/auth/login", json={"email": account["email"], "password": "wrong-password"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_missing_password_is_validation_failed(client) -> None:
    response = client.post("/api/auth/login", json={"email": "owner@payflow.test"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert "password" not in response.text


def test_health(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_support_cannot_approve(db) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from app.modules.auth.models import Membership

    membership = db.scalar(
        select(Membership)
        .options(joinedload(Membership.user), joinedload(Membership.merchant))
        .where(Membership.role == "support")
    )
    try:
        require_owner(membership)
    except AppError as exc:
        assert exc.code == "forbidden"
        assert exc.status_code == 403
    else:
        raise AssertionError("support was allowed to approve")
