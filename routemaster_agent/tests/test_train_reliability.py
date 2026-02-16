from routemaster_agent.intelligence.train_reliability import compute_train_reliability, store_train_reliability, compute_and_store
from routemaster_agent.database.db import SessionLocal
from routemaster_agent.database.models import TrainReliabilityIndex


def test_compute_train_reliability_basic():
    # no drift / no delay -> equals avg_extraction_confidence
    assert compute_train_reliability(avg_extraction_confidence=0.9, schedule_drift_score=0.0, delay_probability=0.0) == 0.9


def test_compute_and_store_and_db_persistence():
    train_no = 'TEST-RELIABILITY-001'
    score = compute_and_store(train_no, avg_extraction_confidence=0.8, schedule_drift_score=0.1, delay_probability=0.05)
    assert score == round(0.8 * (1 - 0.1) * (1 - 0.05), 4)

    # verify DB row inserted
    session = SessionLocal()
    row = session.query(TrainReliabilityIndex).filter(TrainReliabilityIndex.train_number == train_no).order_by(TrainReliabilityIndex.id.desc()).first()
    assert row is not None
    assert abs(row.reliability_score - score) < 1e-6
    session.close()