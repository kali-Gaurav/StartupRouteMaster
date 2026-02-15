"""
Train Reliability index computations (scaffold).
Computes a simple reliability score from historical delay, schedule stability, and extraction confidence.
"""
from typing import Dict


def compute_reliability_score(*, historical_delay_score: float, schedule_stability: float, extraction_confidence: float) -> float:
    """Combine components (all in 0..1) into a reliability score (0..1).
    Weights are configurable later; for now use simple product-weighting.
    """
    # clamp inputs
    hd = max(0.0, min(1.0, historical_delay_score))
    ss = max(0.0, min(1.0, schedule_stability))
    ec = max(0.0, min(1.0, extraction_confidence))
    # simple multiplicative score
    score = hd * ss * ec
    return round(score, 4)
