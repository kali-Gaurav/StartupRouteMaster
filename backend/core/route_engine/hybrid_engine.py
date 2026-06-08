import logging
import numpy as np
from datetime import datetime, timedelta, date
from typing import List, Optional, Any

from .csa_kernel import CSARoutingKernel
from .scoring import RouteScorer
from .constraints import RouteConstraints
from core.data_utils.structures import Route, RouteSegment, TransferConnection, ensure_datetime

logger = logging.getLogger(__name__)

class HybridRouteEngine:
    """
    Subtask 3.6: Hybrid Engine with JIT Multi-Zonal Injection.
    UPGRADED: Returns multiple Pareto-optimal routes as Route objects.
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
                         departure_date: datetime, constraints: RouteConstraints,
                         graph: Optional[Any] = None) -> List[Route]:
        departure_date = ensure_datetime(departure_date)
        # Normalize time to seconds from start of day
        start_time_secs = departure_date.hour * 3600 + departure_date.minute * 60
        
        # CSA Kernel returns List[List[Dict]] (Multiple Pareto paths)
        raw_paths = self.kernel.find_routes(source_stop_id, dest_stop_id, start_time_secs)
        
        if not raw_paths:
            return []

        results = []
        base_date = departure_date.date()
        
        stop_cache = {}
        if graph and hasattr(graph, 'snapshot'):
            stop_cache = graph.snapshot.stop_cache

        for path in raw_paths:
            rt = Route()
            for i, step in enumerate(path):
                # Connection times are seconds from start of day
                dep_dt = ensure_datetime(datetime.combine(base_date, datetime.min.time()) + timedelta(seconds=step['dep_time']))
                arr_dt = ensure_datetime(datetime.combine(base_date, datetime.min.time()) + timedelta(seconds=step['arr_time']), dep_dt)
                
                # Handle midnight rollover (simplified)
                if arr_dt < dep_dt:
                    arr_dt += timedelta(days=1)
                
                seg = RouteSegment(
                    trip_id=step['trip_id'],
                    departure_stop_id=step['dep_stop'],
                    arrival_stop_id=step['arr_stop'],
                    departure_time=dep_dt,
                    arrival_time=arr_dt,
                    duration_minutes=int((arr_dt - dep_dt).total_seconds() / 60),
                    distance_km=0.0, # Will be hydrated by orchestrator
                    train_number=str(step['trip_id']),
                    departure_code=stop_cache[step['dep_stop']].code if step['dep_stop'] in stop_cache else str(step['dep_stop']),
                    arrival_code=stop_cache[step['arr_stop']].code if step['arr_stop'] in stop_cache else str(step['arr_stop'])
                )
                rt.add_segment(seg)
                
                # Add transfer if not the first segment
                if i > 0:
                    prev_seg = rt.segments[-2]
                    prev_arrival = ensure_datetime(prev_seg.arrival_time, ensure_datetime(seg.departure_time))
                    curr_departure = ensure_datetime(seg.departure_time, ensure_datetime(prev_arrival))
                    wait_mins = int((curr_departure - prev_arrival).total_seconds() / 60)
                    tc = TransferConnection(
                        station_id=seg.departure_stop_id,
                        station_code=seg.departure_code,
                        arrival_time=prev_arrival,
                        departure_time=curr_departure,
                        duration_minutes=wait_mins,
                        station_name=seg.departure_code,
                        facilities_score=0.0,
                        safety_score=0.0,
                        platform_from=None,
                        platform_to=None,
                        is_multi_station=False,
                        transfer_type="WALK"
                    )

                    rt.add_transfer(tc)
            
            rt.metadata["engine"] = "hybrid_csa"
            results.append(rt)
            
        return results
