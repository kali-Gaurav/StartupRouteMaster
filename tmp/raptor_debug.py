import asyncio
import sys
import os
from datetime import datetime
import logging

# Setup Logging to see raptor logs
logging.basicConfig(level=logging.INFO)

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.constraints import RouteConstraints
from core.route_engine.base import RoutingRequest

async def debug_raptor():
    engine = RailwayRouteEngine()
    await engine.initialize()
    if not engine.graph:
        print("Failed to initialize engine graph")
        return
        
    raptor = OptimizedRAPTOR()
    
    # NDLS -> MMCT
    src_cluster_ids = [5533]
    dst_cluster_ids = [5080]
    target_date = datetime(2026, 4, 1, 0, 0, 0)
    
    req = RoutingRequest(
        source_code="NDLS",
        destination_code="MMCT",
        departure_date=target_date,
        constraints=RouteConstraints(discovery_only=True),
        limit=10,
        src_cluster_ids=src_cluster_ids,
        dst_cluster_ids=dst_cluster_ids,
        graph=engine.graph
    )
    
    print(f"Running RAPTOR for {target_date}...")
    resp = await raptor.find_routes(req)
    
    print(f"RAPTOR Yield: {resp.yield_count}")
    print(f"RAPTOR Latency: {resp.latency_ms:.2f}ms")
    print(f"Metadata: {resp.metadata}")
    
    # Check pattern_deps manually
    deps = engine.graph.get_pattern_departures(5533, target_date)
    print(f"Manual Pattern Deps count: {len(deps)}")
    
    # Check direct departures
    direct_deps = engine.graph.get_departures_from_stop(5533, target_date)
    print(f"Manual Direct Deps count: {len(direct_deps)}")
    
    reachable_count = 0
    for dt, tid in direct_deps:
        if engine.graph.can_reach_destination(tid, 5080):
            reachable_count += 1
            if reachable_count < 5:
                print(f"Trip {tid} at {dt} IS REACHABLE to MMCT")
    print(f"Total Reachable Trips from NDLS to MMCT (via bitset): {reachable_count}")
    
    total_inst = sum(len(v) for v in deps.values())
    print(f"Total Trip Instances from NDLS: {total_inst}")

if __name__ == "__main__":
    asyncio.run(debug_raptor())
