import os
from datetime import datetime

from routemaster_agent.pipeline.change_detector import compare_schedule_to_db, log_change_if_any
from routemaster_agent.database.db import SessionLocal
from routemaster_agent.database.models import TrainStation, ScheduleChangeLog


def _clear_train(session, train_no: str):
    session.query(TrainStation).filter(TrainStation.train_number == train_no).delete()
    session.query(ScheduleChangeLog).filter(ScheduleChangeLog.train_number == train_no).delete()
    session.commit()


def test_compare_schedule_to_db_detects_added_removed_changed():
    session = SessionLocal()
    train_no = "TEST-CHANGE-001"

    # ensure clean slate
    _clear_train(session, train_no)

    # seed DB snapshot: sequences 1..4 (A, B, C, D)
    db_rows = [
        TrainStation(train_number=train_no, sequence=1, station_code="A", arrival="05:00", departure="05:05"),
        TrainStation(train_number=train_no, sequence=2, station_code="B", arrival="06:00", departure="06:05"),
        TrainStation(train_number=train_no, sequence=3, station_code="C", arrival="07:00", departure="07:05"),
        TrainStation(train_number=train_no, sequence=4, station_code="D", arrival="08:00", departure="08:05"),
    ]
    session.add_all(db_rows)
    session.commit()

    # extracted schedule: change B times, remove C, add X at seq=3
    extracted = {
        "train_no": train_no,
        "name": "TEST",
        "days_of_run": ["Mon"],
        "schedule": [
            {"sequence": 1, "station_code": "A", "arrival": "05:00", "departure": "05:05"},
            {"sequence": 2, "station_code": "B", "arrival": "06:10", "departure": "06:15"},  # changed
            {"sequence": 3, "station_code": "X", "arrival": "07:30", "departure": "07:35"},  # added
            {"sequence": 4, "station_code": "D", "arrival": "08:00", "departure": "08:05"},
        ],
    }

    diff = compare_schedule_to_db(extracted)

    # expectations: one changed (B), one added (X), one removed (C)
    assert diff["train_number"] == train_no
    assert any(s.get("station_code") == "X" for s in diff["added_stations"]) is True
    assert any(s.get("station_code") == "C" for s in diff["removed_stations"]) is True
    assert any(s.get("station_code") == "B" for s in (c.get("station_code") for c in diff["changed_stations"])) is True

    # cleanup
    _clear_train(session, train_no)
    session.close()


def test_log_change_if_any_inserts_schedule_change_log():
    session = SessionLocal()
    train_no = "TEST-CHANGE-002"

    _clear_train(session, train_no)

    # DB seed: A -> B
    db_rows = [
        TrainStation(train_number=train_no, sequence=1, station_code="A", arrival="05:00", departure="05:05"),
        TrainStation(train_number=train_no, sequence=2, station_code="B", arrival="06:00", departure="06:05"),
    ]
    session.add_all(db_rows)
    session.commit()

    # extracted schedule that removes B and adds C
    extracted = {
        "train_no": train_no,
        "name": "TEST",
        "days_of_run": ["Mon"],
        "schedule": [
            {"sequence": 1, "station_code": "A", "arrival": "05:00", "departure": "05:05"},
            {"sequence": 2, "station_code": "C", "arrival": "06:30", "departure": "06:35"},
        ],
    }

    diff = log_change_if_any(extracted)

    # should have created a ScheduleChangeLog entry
    assert diff.get("logged_id") is not None
    entry = session.query(ScheduleChangeLog).get(diff.get("logged_id"))
    assert entry is not None
    assert entry.train_number == train_no
    assert entry.diff["train_number"] == train_no

    # cleanup
    _clear_train(session, train_no)
    session.close()
