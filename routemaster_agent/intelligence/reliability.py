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


def compute_extraction_confidence(*, selector_confidence: float = 1.0, retry_count: int = 0, validation_pass_rate: float = 1.0, proxy_health_score: float = 1.0) -> float:
    """Compute a bounded extraction confidence (0.0 - 1.0).

    Components:
    - selector_confidence: heuristic confidence for the selector (0..1)
    - retry_count: number of retries attempted (penalized exponentially)
    - validation_pass_rate: fraction of validation checks that passed (0..1)
    - proxy_health_score: proxy health (0..1)

    Formula: selector_confidence * (0.9 ** retry_count) * validation_pass_rate * proxy_health_score
    """
    sc = max(0.0, min(1.0, float(selector_confidence or 0.0)))
    vpr = max(0.0, min(1.0, float(validation_pass_rate or 0.0)))
    phs = max(0.0, min(1.0, float(proxy_health_score or 0.0)))
    rc = max(0, int(retry_count or 0))
    retry_penalty = 0.9 ** rc
    score = sc * retry_penalty * vpr * phs
    return round(score, 4)

