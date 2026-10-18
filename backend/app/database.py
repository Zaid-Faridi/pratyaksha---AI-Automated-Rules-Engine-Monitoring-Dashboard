"""
Database Connection and Session Management using SQLAlchemy.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# Configure SQLite vs PostgreSQL connection arguments
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
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
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_detection_events_event_id ON detection_events (event_id)"))
        except Exception:
            pass

