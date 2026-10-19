"""
Database Connection and Session Management using SQLAlchemy.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

from sqlalchemy.pool import NullPool

# Configure SQLite vs PostgreSQL connection arguments
connect_args = {}
engine_kwargs = {"echo": False}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 40

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from sqlalchemy import text


def init_db() -> None:
    """Create all tables and auto-migrate missing columns."""
    Base.metadata.create_all(bind=engine)

    # Lightweight auto-migrations for newly added columns
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN edge_metadata JSON DEFAULT '{}'"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE detection_events ADD COLUMN event_id VARCHAR(64)"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE centres ADD COLUMN live_streaming_enabled BOOLEAN DEFAULT 1"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE detection_events ADD COLUMN is_reliable BOOLEAN DEFAULT 1"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE detection_events ADD COLUMN quality_metrics JSON DEFAULT '{}'"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE detection_events ADD COLUMN compliance_metrics JSON DEFAULT '{}'"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE centres ADD COLUMN trade_id VARCHAR(64)"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE centres ADD COLUMN trade_overrides JSON DEFAULT '{}'"))
        except Exception:
            pass
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_detection_events_event_id ON detection_events (event_id)"))
        except Exception:
            pass

