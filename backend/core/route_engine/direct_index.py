import logging
from typing import List, Dict, Tuple, Set
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class DirectRouteManager:
    """
    Task 22: Level 0 - Direct Pre-computation.
    Maintains an O(1) index for direct (0-transfer) routes.
    """
    
    def __init__(self, db: Session):
        self.db = db
        # (source_id, dest_id) -> List[trip_id]
        self._index: Dict[Tuple[int, int], Set[int]] = defaultdict(set)
        self.is_initialized = False

    def build_index(self):
        """Pre-computes the direct route map from segments table."""
        logger.info("Building Direct Route Index (Level 0)...")
        # Optimization: only index trips, not every individual segment
        query = text("""
            SELECT trip_id, source_station_id, dest_station_id 
            FROM segments
        """)
        rows = self.db.execute(query).fetchall()
        for tid, src, dst in rows:
            self._index[(int(src), int(dst))].add(int(tid))
        
        self.is_initialized = True
        logger.info(f"Direct Index built with {len(self._index)} OD pairs.")

    def get_direct_trips(self, source_id: int, dest_id: int) -> List[int]:
        """Returns all trip IDs that go directly from source to destination."""
        return list(self._index.get((source_id, dest_id), []))

# Global instance for the engine
direct_route_manager = None

def get_direct_manager(db: Session):
    global direct_route_manager
    if direct_route_manager is None:
        direct_route_manager = DirectRouteManager(db)
        direct_route_manager.build_index()
    return direct_route_manager
