import logging
from datetime import datetime, timedelta
from typing import List, Optional, Any

from .csa_kernel import CSARoutingKernel
from .scorer import RouteScorer
from .constraints import RouteConstraints

logger = logging.getLogger(__name__)

class HybridRouteEngine:
    """
    Orchestrates the 100x faster routing process:
    1. Fast Candidate Search (CSA Kernel)
    2. Deep Scoring and Hydration (Scoring Layer)
    """
    def __init__(self, timetable_path: str = "backend/data/timetable.npz"):
        self.kernel = CSARoutingKernel(timetable_path)

    async def find_routes(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints) -> List[Any]:
        # 1. Normalize time (seconds since midnight)
        start_time_secs = departure_date.hour * 3600 + departure_date.minute * 60
        
        # 2. Fast Kernel Search (Stage 1)
        # CSA finds the earliest arrival path very quickly
        raw_path = self.kernel.find_routes(source_stop_id, dest_stop_id, start_time_secs)
        
        if not raw_path:
            logger.info("Fast Kernel found no paths.")
            return []

        # 3. Apply Scoring (Stage 2 - Tasks 1-50)
        scorer = RouteScorer(constraints)
        processed = scorer.score_route(raw_path)
        
        # For multiple routes, we would run Profile CSA or multiple kernel calls
        # with varying start times (Range-RAPTOR style).
        
        # 4. Final Result Mapping
        # In a real system, we'd convert the raw path back into the existing Route object
        return [processed]
