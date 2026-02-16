import pytest
from sqlalchemy import create_engine, text

import backend.services.routemaster_client as rmc
import backend.database as bdb


@pytest.mark.asyncio
async def test_get_train_reliabilities_reads_db_and_falls_back(monkeypatch):
    # Prepare an isolated in-memory engine and monkeypatch backend.database.engine
    engine = create_engine("sqlite:///:memory:")
    monkeypatch.setattr(bdb, "engine", engine)

    # Create minimal train_reliability_index table and insert a test row
    with engine.connect() as conn:
        conn.execute(text(
            """
            CREATE TABLE train_reliability_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                train_number TEXT,
                reliability_score FLOAT,
                avg_extraction_confidence FLOAT,
                schedule_drift_score FLOAT,
                delay_probability FLOAT,
                computed_at DATETIME,
                window_minutes INTEGER
            )
            """
        ))
        conn.execute(text(
            "INSERT INTO train_reliability_index (train_number, reliability_score, computed_at) VALUES ('12345', 0.42, '2026-01-01 00:00:00')"
        ))

    # Call the async function
    out = await rmc.get_train_reliabilities(["12345", "99999"])

    # Known train should return stored value; unknown should default to 1.0 (fail-open)
    assert out["12345"] == pytest.approx(0.42)
    assert out["99999"] == 1.0
