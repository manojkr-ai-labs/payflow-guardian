from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import Settings, load_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def enable_sqlite_savepoints(engine: Engine) -> None:
    """Keep SAVEPOINT inside the real transaction.

    The sqlite3 driver otherwise commits on RELEASE SAVEPOINT, which would store
    an order before PayPal returns and before the activity row is written.
    """

    @event.listens_for(engine, "connect")
    def _do_connect(dbapi_connection, _connection_record) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _do_begin(conn) -> None:
        conn.exec_driver_sql("BEGIN")


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        # In-memory tests share one connection. A file database gives each session
        # its own connection so one request cannot open BEGIN inside another.
        memory = ":memory:" in url
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=StaticPool if memory else NullPool,
        )
        enable_sqlite_savepoints(engine)
        return engine
    return create_engine(url, pool_pre_ping=True)


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = make_engine(get_settings().database_url)
        _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def get_db():
    db = get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
