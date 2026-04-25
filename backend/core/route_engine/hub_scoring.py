import logging
import math
from sqlalchemy import text, func
from datetime import datetime
from typing import List, Dict, Any, Tuple, cast

from database.session import SessionTransit
from database.models import Stop, StationRank, StopTime, Trip

logger = logging.getLogger("hub-scoring")

class StationScoringEngine:
    def __init__(self):
        self.db = SessionTransit()

    def calculate_all_ranks(self, force: bool = False):
        if not force:
            stop_model = cast(Any, Stop)
            count = self.db.query(Stop).filter(stop_model.connectivity_score > 0).count()
            if count > 100:
                logger.info(f"⏩ skipping scoring: {count} stations already have scores.")
                return

        logger.info("🚀 Starting Vectorized Station Audit for Hub Scoring...")
        try:
            import numpy as np
            stops = self.db.query(Stop).all()
            total = len(stops)
            
            # 1. Gather Data into Arrays
            train_counts_raw = self._get_daily_train_counts()
            conn_map_raw = self._get_connectivity_map()
            
            # Prepare arrays for vectorized computation
            # Indices will map to stop IDs
            stop_ids = np.array([s.id for s in stops], dtype=np.int32)
            train_counts = np.array([train_counts_raw.get(sid, 0) for sid in stop_ids], dtype=np.float32)
            conn_counts = np.array([conn_map_raw.get(sid, 0) for sid in stop_ids], dtype=np.float32)
            is_major = np.array([1.0 if getattr(s, 'is_major_junction', False) else 0.0 for s in stops], dtype=np.float32)
            
            # 2. Vectorized Math (Task 24)
            # freq_score: Log10(1500) * 12 = ~3.1 * 12 = ~37
            freq_scores = np.log10(train_counts + 1) * 12.0
            
            # conn_score: Log10(5000) * 15 = ~3.7 * 15 = ~55
            conn_scores = np.log10(conn_counts + 1) * 15.0
            
            # Total Score
            final_scores = freq_scores + conn_scores + (is_major * 8.0)
            final_scores = np.clip(final_scores, 0.0, 100.0)
            
            # 3. Apply Results Back to models (Batch Update)
            for i, stop in enumerate(stops):
                score = round(float(final_scores[i]), 2)
                hub_type = "regular"
                if score > 90: hub_type = "mega_hub"
                elif score > 75: hub_type = "major_hub"
                elif score > 55: hub_type = "regional_hub"
                
                setattr(stop, "connectivity_score", score)
                setattr(stop, "hub_type", hub_type)
                
                # Check for existing rank record or create new
                # (Still synchronous but loop is lean)
            
            self.db.commit()
            logger.info(f"✅ Vectorized audit complete: Ranked {total} stations.")
        except Exception as e:
            logger.error(f"Station scoring failed: {e}")
            self.db.rollback()
        finally:
            self.db.close()

    def _get_daily_train_counts(self) -> Dict[int, int]:
        query = text("SELECT stop_id, COUNT(DISTINCT trip_id) as train_count FROM stop_times GROUP BY stop_id")
        results = self.db.execute(query).fetchall()
        return {row[0]: row[1] for row in results}

    def _get_connectivity_map(self) -> Dict[int, int]:
        query = text("""
            SELECT s1.stop_id, COUNT(DISTINCT s2.stop_id) as connectivity
            FROM stop_times s1
            JOIN stop_times s2 ON s1.trip_id = s2.trip_id
            WHERE s1.stop_sequence < s2.stop_sequence
            GROUP BY s1.stop_id
        """)
        results = self.db.execute(query).fetchall()
        return {row[0]: row[1] for row in results}

if __name__ == "__main__":
    import asyncio
    from database.session import initialize_database_pools
    async def run_scoring():
        await initialize_database_pools()
        engine = StationScoringEngine()
        engine.calculate_all_ranks(force=True)
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scoring())
