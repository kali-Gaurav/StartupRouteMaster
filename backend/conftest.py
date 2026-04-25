# Ensure repository root is on sys.path so tests can import `backend` package when running from `backend/`
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Removed backend.api aliasing

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
    _gasqlite = None
    _orig_after_create = None
    try:
        import geoalchemy2.admin.dialects.sqlite as _gasqlite
        _orig_after_create = getattr(_gasqlite, 'after_create', None)
        _gasqlite.after_create = lambda *a, **kw: None
    except Exception:
        _gasqlite = None
        _orig_after_create = None

    Base.metadata.create_all(bind=engine)

    # restore if we changed it
    if _gasqlite is not None and _orig_after_create is not None:
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
    import app as _app_module
    _app_module.app.dependency_overrides[get_db] = lambda: (session)

    yield session

    # Teardown
    session.close()
    engine.dispose()
