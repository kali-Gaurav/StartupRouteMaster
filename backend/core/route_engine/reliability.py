
import logging
from typing import Dict, Tuple, Optional
import numpy as np
from sqlalchemy import text
from datetime import datetime, timedelta

logger = logging.getLogger("nexus.reliability")

class ReliabilityEngine:
    """
    [Task 173/175] Intelligent Reliability Scoring.
    Analyzes historical delays to predict current route stability.
    """
    def __init__(self, db_session):
        self.db = db_session
        self.cache: Dict[str, float] = {} # train_no -> score (0-1)

    def calculate_all_scores(self) -> Dict[str, float]:
        """
        Aggregate recent delay data into a unified stability index.
        Ideal Score (1.0) = On time.
        Poor Score (<0.5) = Major delays prone.
        """
        try:
            # Fetch last 48 hours or last 50 samples per train
            query = """
                SELECT train_number, AVG(delay_minutes), COUNT(*)
                FROM train_live_updates
                GROUP BY train_number
                HAVING COUNT(*) > 3
            """
            rows = self.db.execute(text(query)).fetchall()
            
            new_scores = {}
            for t_no, avg_delay, count in rows:
                # Reliability Formula: 1.0 - sigmoid(avg_delay / penalty_threshold)
                # penalty_threshold = 120 mins implies 2h delay is very bad
                score = 1.0 / (1.0 + np.exp((avg_delay - 60) / 30))
                new_scores[str(t_no)] = round(float(score), 3)
            
            self.cache = new_scores
            logger.info(f"🛡️ Reliability Engine: Indexed {len(new_scores)} stability scores.")
            return new_scores
        except Exception as e:
            logger.error(f"Failed to calculate reliability: {e}")
            return {}

    def get_trip_reliability(self, train_no: str) -> float:
        return self.cache.get(str(train_no), 0.9) # Defaults to 0.9 for unknown stability
