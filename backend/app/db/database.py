"""
Database engine and session factory.

Tries PostgreSQL first; if the connection fails (DNS / timeout / auth),
automatically falls back to a local SQLite file so the app still starts.
Uses NullPool for PostgreSQL to avoid stale PgBouncer connections.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


def _build_engine():
    """
    Build the SQLAlchemy engine.
    Attempt PostgreSQL first; on ANY failure fall back to local SQLite.
    """
    url = settings.DATABASE_URL

    if url.startswith("postgresql"):
        try:
            pg_engine = create_engine(
                url,
                poolclass=NullPool,
                connect_args={"connect_timeout": 5},
                echo=False,
            )
            # Verify that we can actually reach the database
            with pg_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"[OK] Connected to PostgreSQL")
            return pg_engine
        except Exception as exc:
            print(f"[WARNING] PostgreSQL connection failed: {exc}")
            print("[WARNING] Falling back to local SQLite database.")
            url = "sqlite:///./performbharat.db"

    # SQLite (either originally configured or fallback)
    return create_engine(
        url,
        connect_args={"check_same_thread": False},
        echo=False,
    )


engine = _build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
