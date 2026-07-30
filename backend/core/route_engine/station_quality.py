import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class StationQualityManager:
    """
    Analyzes station metadata (facilities, safety) to provide normalized scores.
    Scores are in range [0.0, 10.0].
    """

    FACILITY_WEIGHTS = {
        "wifi": 1.0,
        "lounge": 2.5,
        "food": 1.5,
        "accessible": 2.0,
        "parking": 0.5,
        "waiting_room": 1.5,
        "lift": 1.0
    }

    @classmethod
    def calculate_facility_score(cls, facilities_json: Dict[str, Any]) -> float:
        """Calculate a facility score based on available amenities."""
        if not facilities_json:
            return 5.0 # Neutral fallback
        
        total_possible = sum(cls.FACILITY_WEIGHTS.values())
        score = 0.0
        
        for key, weight in cls.FACILITY_WEIGHTS.items():
            if facilities_json.get(key) is True:
                score += weight
        
        # Normalize to 0-10
        return (score / total_possible) * 10.0

    @classmethod
    def normalize_safety_score(cls, raw_safety: float) -> float:
        """Ensure safety score is within 0-10 range."""
        # Assume DB safety is 0-100
        return max(0.0, min(10.0, raw_safety / 10.0))
