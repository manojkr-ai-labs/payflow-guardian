import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SESSION_SECRET"] = "test-session-secret"
os.environ["PAYPAL_CLIENT_ID"] = "test-client-id"
os.environ["PAYPAL_CLIENT_SECRET"] = "test-client-secret"
os.environ["PAYPAL_API_BASE"] = "https://api-m.sandbox.paypal.com"
os.environ["WEB_ORIGIN"] = "http://localhost:3000"
os.environ["PAYFLOW_SKIP_SEED"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.db import Base, get_engine, get_session_factory
from app.main import create_app
from app.modules.activity import models as activity_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.payments import models as payment_models  # noqa: F401
from app.modules.auth.seed import seed_demo


def _prepare_database() -> None:
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = get_session_factory()()
    try:
        seed_demo(session)
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def db() -> Session:
    _prepare_database()
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(get_engine())


@pytest.fixture()
def client() -> TestClient:
    _prepare_database()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(get_engine())
