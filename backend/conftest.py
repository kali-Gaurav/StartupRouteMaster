# Ensure repository root is on sys.path so tests can import `backend` package when running from `backend/`
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Make `api.*` imports resolve to `backend.api.*` so tests that import `api.chat` patch the same modules
import importlib
_backend_api = importlib.import_module("backend.api")
import sys as _sys
_sys.modules['api'] = _backend_api
# Also alias commonly-used submodules so tests that import `api.*` get the same module objects
try:
    _backend_chat = importlib.import_module("backend.api.chat")
    _sys.modules['api.chat'] = _backend_chat
except Exception:
    pass

import json
import pytest
from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from database.models import Stop

# Any shared pytest fixtures can be added here later (db, client, test data)


@pytest.fixture(scope="session")
def db():
    """Provide a test database session and seed station_master for station search tests."""
    # Create a thread-shared in-memory SQLite DB for tests (StaticPool + check_same_thread=False)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Avoid geoalchemy2 DDL calls which require SpatiaLite/PostGIS in sqlite
    try:
        import geoalchemy2.dialects.sqlite as _gasqlite
        _orig_after_create = getattr(_gasqlite, 'after_create', None)
        _gasqlite.after_create = lambda *a, **kw: None
    except Exception:
        _orig_after_create = None

    Base.metadata.create_all(bind=engine)

    # restore if we changed it
    if _orig_after_create is not None:
        _gasqlite.after_create = _orig_after_create

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Seed a small set of stations required by tests (keeps test fast)
    stations = [
        {"code": "KOTA", "name": "Kota Junction", "city": "Kota", "state": "Rajasthan", "latitude": 0.0, "longitude": 0.0},
        {"code": "PALAK", "name": "PALAKKAD JN", "city": "Palakkad", "state": "Kerala", "latitude": 0.0, "longitude": 0.0},
        {"code": "JP", "name": "Jaipur Junction", "city": "Jaipur", "state": "Rajasthan", "latitude": 0.0, "longitude": 0.0},
        {"code": "NDLS", "name": "New Delhi Railway Station", "city": "Delhi", "state": "Delhi", "latitude": 0.0, "longitude": 0.0},
        {"code": "BCT", "name": "Mumbai Central", "city": "Mumbai", "state": "Maharashtra", "latitude": 0.0, "longitude": 0.0},
        {"code": "MUM", "name": "Mumbai", "city": "Mumbai", "state": "Maharashtra", "latitude": 0.0, "longitude": 0.0},
    ]

    for s in stations:
        session.add(Stop(**s))
    session.commit()

    # Override FastAPI dependency so endpoints use this test session
    from backend import app as _app_module
    _app_module.app.dependency_overrides[get_db] = lambda: (session)

    yield session

    # Teardown
    session.close()
    engine.dispose()
