import logging
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Any

from .csa_kernel import CSARoutingKernel
from .scorer import RouteScorer
from .constraints import RouteConstraints

logger = logging.getLogger(__name__)

class HybridRouteEngine:
    """
    Subtask 3.6: Hybrid Engine with JIT Multi-Zonal Injection.
    """
    def __init__(self, timetable_path: str = "backend/data/timetable.npz"):
        self.kernel = CSARoutingKernel(timetable_path)

    def update_graph_jit(self, stitched_data: np.ndarray):
        """Update core kernel with optimized zonal data."""
        self.kernel.inject_stitched_data(stitched_data)

    def reset_graph(self):
        """Reset kernel to the global search space."""
        self.kernel.reset_to_global()

    async def find_routes(self, source_stop_id: int, dest_stop_id: int,
                         departure_date: datetime, constraints: RouteConstraints) -> List[Any]:
        # Normalize time
        start_time_secs = departure_date.hour * 3600 + departure_date.minute * 60
        
        # Search using CURRENT state of kernel (could be global or stitched)
        raw_path = self.kernel.find_routes(source_stop_id, dest_stop_id, start_time_secs)
        
        if not raw_path:
            return []

        scorer = RouteScorer(constraints)
        processed = scorer.score_route(raw_path)
        
        return [processed]
