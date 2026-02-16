from datetime import datetime
from typing import Optional, List, Dict

from routemaster_agent.intelligence.reliability import compute_reliability_score
from routemaster_agent.database.db import SessionLocal
from routemaster_agent.database.models import TrainReliabilityIndex
from routemaster_agent.metrics import RMA_TRAIN_RELIABILITY_SCORE


def compute_train_reliability(*, avg_extraction_confidence: float, schedule_drift_score: float = 0.0, delay_probability: float = 0.0) -> float:
    """Deterministic reliability formula (v1):

    reliability = avg_extraction_confidence * (1 - schedule_drift_score) * (1 - delay_probability)

    All inputs are clamped to 0..1 by compute_reliability_score where applicable.
    """
    # Clamp inputs to 0..1
    aec = max(0.0, min(1.0, float(avg_extraction_confidence or 0.0)))
    sds = max(0.0, min(1.0, float(schedule_drift_score or 0.0)))
    dp = max(0.0, min(1.0, float(delay_probability or 0.0)))

    score = aec * (1.0 - sds) * (1.0 - dp)
    return round(score, 4)


def store_train_reliability(train_number: str, *, reliability_score: float, avg_extraction_confidence: Optional[float] = None, schedule_drift_score: Optional[float] = None, delay_probability: Optional[float] = None, window_minutes: int = 60):
    """Persist reliability record and update Prometheus gauge."""
    db = SessionLocal()
    try:
        rec = TrainReliabilityIndex(
            train_number=train_number,
            reliability_score=reliability_score,
            avg_extraction_confidence=(avg_extraction_confidence or 0.0),
            schedule_drift_score=(schedule_drift_score or 0.0),
            delay_probability=(delay_probability or 0.0),
            computed_at=datetime.utcnow(),
            window_minutes=window_minutes,
        )
        db.add(rec)
        db.commit()
    finally:
        db.close()

    try:
        RMA_TRAIN_RELIABILITY_SCORE.labels(train_number=train_number).set(reliability_score)
    except Exception:
        pass


# convenience function that computes + stores
def compute_and_store(train_number: str, *, avg_extraction_confidence: float, schedule_drift_score: float = 0.0, delay_probability: float = 0.0, window_minutes: int = 60) -> float:
    score = compute_train_reliability(avg_extraction_confidence=avg_extraction_confidence, schedule_drift_score=schedule_drift_score, delay_probability=delay_probability)
    store_train_reliability(train_number, reliability_score=score, avg_extraction_confidence=avg_extraction_confidence, schedule_drift_score=schedule_drift_score, delay_probability=delay_probability, window_minutes=window_minutes)
    return score


def get_train_reliabilities(train_numbers: List[str]) -> Dict[str, float]:
    """Get latest reliability scores for a list of train numbers.
    
    Returns a dict mapping train_number -> reliability_score.
    If no reliability data exists for a train, returns 1.0 (neutral/default).
    """
    db = SessionLocal()
    try:
        # Get the latest reliability record for each train
        results = {}
        for train_no in train_numbers:
            row = db.query(TrainReliabilityIndex).filter(
                TrainReliabilityIndex.train_number == train_no
            ).order_by(TrainReliabilityIndex.id.desc()).first()
            
            if row:
                results[train_no] = row.reliability_score
            else:
                results[train_no] = 1.0  # Default neutral score
        
        return results
    finally:
        db.close()