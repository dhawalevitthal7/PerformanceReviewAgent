"""
Database engine and session factory.

Tries PostgreSQL first; if the connection fails (DNS / timeout / auth)
at any point — startup probe, table creation, or a live request — the
module transparently switches to a local SQLite fallback so the app
remains usable for local development.

Uses NullPool for PostgreSQL to avoid stale PgBouncer connections.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import default_sqlite_url, settings


def _make_sqlite_engine():
    return create_engine(
        default_sqlite_url(),
        connect_args={"check_same_thread": False},
        echo=False,
    )


def _make_pg_engine(url: str):
    return create_engine(
        url,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5},
        echo=False,
    )


def _build_engine():
    """
    Build the SQLAlchemy engine, falling back to SQLite on any failure.
    """
    url = settings.DATABASE_URL

    if url.startswith("postgresql"):
        try:
            pg_engine = _make_pg_engine(url)
            with pg_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[OK] Connected to PostgreSQL")
            return pg_engine
        except Exception as exc:
            print(f"[WARNING] PostgreSQL connection failed: {exc}")
            print("[WARNING] Falling back to local SQLite database.")

    return _make_sqlite_engine()


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def switch_to_sqlite() -> None:
    """
    Replace the global engine and session factory with a SQLite engine.
    Called by init_database() when the PostgreSQL engine can no longer
    execute DDL (e.g. DNS failure after initial startup).
    """
    global engine, SessionLocal  # noqa: PLW0603
    if not str(engine.url).startswith("sqlite"):
        print("[WARNING] Switching runtime engine to local SQLite database.")
        engine = _make_sqlite_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
