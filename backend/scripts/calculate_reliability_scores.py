"""
[Missing Logic #7] calculate_reliability_scores.py

Aggregates StationTrainHistory to calculate on-time percentage (reliability_score)
per train at each station.
"""

import logging
from sqlalchemy import func
from database.session import SessionLocal
from database.models import StationTrainHistory, Trip, Stop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reliability-calc")

def calculate_reliability():
    session = SessionLocal()
    try:
        # Calculate reliability score: (count of on-time) / (total count)
        # On-time defined as delay <= 15 minutes for this purpose
        
        # Using SQLAlchemy query to aggregate
        results = session.query(
            StationTrainHistory.trip_id,
            StationTrainHistory.station_id,
            func.count(StationTrainHistory.id).label("total"),
            func.sum(func.case([(StationTrainHistory.delay_minutes <= 15, 1)], else_=0)).label("on_time")
        ).group_by(
            StationTrainHistory.trip_id,
            StationTrainHistory.station_id
        ).all()
        
        scores = {}
        for tid, sid, total, on_time in results:
            score = (on_time / total) if total > 0 else 1.0
            scores[(tid, sid)] = score
            
        logger.info(f"Calculated reliability scores for {len(scores)} trip-station pairs.")
        return scores
        
    except Exception as e:
        logger.error(f"Reliability calculation failed: {e}")
        return {}
    finally:
        session.close()

if __name__ == "__main__":
    calculate_reliability()
