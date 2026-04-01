import sys
import os
import asyncio
from datetime import datetime
sys.path.append(os.getcwd())

from core.route_engine.engine import route_engine
from core.route_engine.graph import TimeDependentGraph

async def check_raptor_data():
    await route_engine.init(date_override=datetime(2026, 4, 1))
    graph = route_engine.graph
    
    # NDLS ID is 5533 (based on my previous check)
    # Let's get the real ID from the graph
    stop = graph.get_stop_by_code('NDLS')
    if not stop:
        print("NDLS not found in graph")
        return
    
    sid = stop.id
    print(f"NDLS ID in graph: {sid}")
    
    # Check departures
    dep_dt = datetime(2026, 4, 1, 10, 0)
    deps = graph.get_pattern_departures(sid, dep_dt, lookahead=1440)
    print(f"NDLS Departures count (Pattern): {len(deps)}")
    
    # Check reachability for NDLS->MMCT
    mmct_stop = graph.get_stop_by_code('MMCT')
    if mmct_stop:
        # Trip for Mumbai Rajdhani (12952) is 2003
        reachable = graph.can_reach_destination(2003, mmct_stop.id)
        print(f"Is MMCT ({mmct_stop.id}) reachable from trip 2003? {reachable}")
    
    # Check if MMCT exists in snapshot map
    if mmct_stop and mmct_stop.id in graph.snapshot._stop_id_map:
        print(f"MMCT ID {mmct_stop.id} is in snapshot stop_id_map")
    else:
        print(f"MMCT ID {mmct_stop.id} NOT in map!")

if __name__ == "__main__":
    asyncio.run(check_raptor_data())
