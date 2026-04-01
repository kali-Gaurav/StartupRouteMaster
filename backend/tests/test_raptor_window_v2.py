import sys
import os
import asyncio
from datetime import datetime, timedelta
import logging
import numpy as np

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.graph import TimeDependentGraph, StaticGraphSnapshot
from core.route_engine.constraints import RouteConstraints
from core.data_structures import RouteSegment

async def test_raptor_24h_window_deep():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test-raptor")
    
    # 1. Setup Mock Graph
    base_date = datetime(2026, 3, 20, 10, 0, 0) 
    dep_time = datetime(2026, 3, 20, 23, 30, 0)
    arr_time = datetime(2026, 3, 21, 10, 30, 0)
    
    seg = RouteSegment(
        trip_id=101, departure_stop_id=1, arrival_stop_id=2,
        departure_time=dep_time, arrival_time=arr_time,
        duration_minutes=660, distance_km=1400.0,
        departure_code="DEL", arrival_code="BUM",
        service_mask=127 
    )
    
    snapshot = StaticGraphSnapshot(date=base_date)
    snapshot.departures_by_stop[1] = [(dep_time, 101)]
    snapshot.trip_segments[101] = [seg]
    
    # Setup pattern index manually for test
    # pattern for trip 101 is (1, 2)
    pid = hash((1, 2)) & 0x7FFFFFFF
    snapshot._pattern_deps_data = np.array([[pid, int(dep_time.timestamp()), 101]], dtype=np.int64)
    snapshot._pattern_deps_index = np.array([[0, 1]], dtype=np.int32)
    snapshot._stop_id_map = {1: 0}
    
    snapshot._segments_data = np.array([[
        101, 1, 2, int(dep_time.timestamp()), int(arr_time.timestamp()), 1400000, 127
    ]], dtype=np.int64)
    snapshot._segments_index = np.array([[0, 1]], dtype=np.int32)
    snapshot._trip_id_map = {101: 0}
    
    graph = TimeDependentGraph(snapshot)
    raptor = OptimizedRAPTOR(max_transfers=1)
    
    # 2. Run Query
    constraints = RouteConstraints(range_minutes=1440) 
    logger.info("Running RAPTOR 24h Window Deep Test...")
    
    routes = await raptor.find_routes(1, 2, base_date, constraints, graph=graph)
    
    # 3. Assertions
    if len(routes) > 0:
        logger.info(f"✅ SUCCESS: Found {len(routes)} routes.")
        for r in routes:
            logger.info(f"Route: Dep {r.segments[0].departure_time}, Arr {r.segments[-1].arrival_time}")
            assert r.segments[0].trip_id == 101
    else:
        logger.error("❌ FAILURE: No routes found in 24h window.")
        sys.exit(1)


def test_raptor_frontier_multiplier_tuning():
    raptor = OptimizedRAPTOR(max_transfers=3)
    assert raptor.round_frontier_multipliers[1] <= 2.0
    assert raptor.round_frontier_multipliers[2] <= 3.0


if __name__ == "__main__":
    asyncio.run(test_raptor_24h_window_deep())
