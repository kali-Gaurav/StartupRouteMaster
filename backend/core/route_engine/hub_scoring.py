import logging
import math
from sqlalchemy import text, func
from datetime import datetime
from typing import List, Dict, Any, Tuple

from database.session import SessionTransit
from database.models import Stop, StationRank, StopTime, Trip

logger = logging.getLogger("hub-scoring")

class StationScoringEngine:
    def __init__(self):
        self.db = SessionTransit()

    def calculate_all_ranks(self, force: bool = False):
        if not force:
            count = self.db.query(Stop).filter(Stop.connectivity_score > 0).count()
            if count > 100:
                logger.info(f"⏩ skipping scoring: {count} stations already have scores.")
                return

        logger.info("🚀 Starting Global Station Audit for Hub Scoring...")
        try:
            stops = self.db.query(Stop).all()
            total = len(stops)
            train_counts = self._get_daily_train_counts()
            connectivity_map = self._get_connectivity_map()

            processed = 0
            for stop in stops:
                # REFINED STRICT LOGIC
                train_count = train_counts.get(stop.id, 0)
                # freq_score: Log10(1500) * 12 = ~3.1 * 12 = ~37
                freq_score = math.log10(train_count + 1) * 12 
                
                unique_dests = connectivity_map.get(stop.id, 0)
                # conn_score: Log10(5000) * 15 = ~3.7 * 15 = ~55
                conn_score = math.log10(unique_dests + 1) * 15
                
                junction_bonus = 8 if getattr(stop, 'is_major_junction', False) else 0
                
                # Total before normalization: ~37 + 55 + 8 = 100
                final_score = freq_score + conn_score + junction_bonus
                
                # Normalize strictly
                final_score = min(100.0, max(0.0, final_score))
                
                hub_type = "regular"
                if final_score > 90: hub_type = "mega_hub"
                elif final_score > 75: hub_type = "major_hub"
                elif final_score > 55: hub_type = "regional_hub"

                stop.connectivity_score = round(final_score, 2)
                stop.hub_type = hub_type

                rank = self.db.query(StationRank).filter(StationRank.station_id == stop.id).first()
                if not rank:
                    rank = StationRank(station_id=stop.id)
                    self.db.add(rank)
                rank.connectivity_score = stop.connectivity_score
                rank.hub_type = hub_type
                
                processed += 1
                if processed % 1000 == 0:
                    logger.info(f"Scoring Progress: {processed}/{total}")
            
            self.db.commit()
            logger.info(f"✅ Successfully audited and ranked {total} stations.")
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
