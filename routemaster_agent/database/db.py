import os
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

# Use DATABASE_URL env var for Postgres in production, fallback to SQLite for dev.
DATABASE_URL = os.getenv("RMA_DATABASE_URL") or os.getenv("DATABASE_URL") or "sqlite:///./backend/database/transit_graph.db"

# SQLite needs a special connect_arg; other DBs do not.
if DATABASE_URL.startswith("sqlite:"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Lazily initialize local SQLite schema by default so core jobs/tests do not fail with
# "no such table" errors. In production (Postgres), schema should still be migration-managed.
_AUTO_INIT_SQLITE = os.getenv("RMA_AUTO_INIT_SQLITE_SCHEMA", "true").lower() in ("1", "true", "yes")
_schema_initialized = False
_schema_lock = Lock()


def _ensure_schema() -> None:
    global _schema_initialized
    if _schema_initialized:
        return

    if not (DATABASE_URL.startswith("sqlite:") and _AUTO_INIT_SQLITE):
        _schema_initialized = True
        return

    with _schema_lock:
        if _schema_initialized:
            return
        Base.metadata.create_all(bind=engine)
        _schema_initialized = True


def get_db():
    _ensure_schema()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Ensure schema for direct SessionLocal() call sites as well.
_ensure_schema()
