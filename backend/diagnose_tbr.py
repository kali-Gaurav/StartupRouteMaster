import asyncio
import logging
from datetime import datetime, timedelta
from core.route_engine.tbr_router import TripBasedRouter
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona
from database.session import SessionTransit, initialize_database_pools
from core.route_engine.engine import RailwayRouteEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("diagnose_tbr")

async def diagnose(src_code, dst_code):
    print(f"DIAGNOSING TBR: {src_code} -> {dst_code}")
    await initialize_database_pools()
    tbr = TripBasedRouter()
    date = datetime.now() + timedelta(days=2)
    graph = await tbr.get_graph(date)
    
    src_stop = graph.get_stop_by_code(src_code)
    dst_stop = graph.get_stop_by_code(dst_code)
    
    if not src_stop or not dst_stop:
        print(f"ERROR: Could not find stops")
        return

    print(f"Source ID: {src_stop.id}, Dest ID: {dst_stop.id}")
    
    # Check edges
    if tbr._edges is None:
        print("ERROR: _edges is None")
    else:
        print(f"Edges loaded: {len(tbr._edges)}")
        
    if not tbr._edge_lookup_map:
        print("ERROR: _edge_lookup_map is empty")
    else:
        print(f"Edge lookup entries: {len(tbr._edge_lookup_map)}")

    # Check departures
    deps = graph.get_departures_from_stop(src_stop.id, date, 1440)
    print(f"Departures from source: {len(deps)}")
    
    if deps:
        print(f"Sample departure: {deps[0]}")
        tid = deps[0][1]
        
        # Check reachability bitset
        can_reach = graph.can_reach_destination(tid, dst_stop.id)
        print(f"Trip {tid} can reach destination bitset: {can_reach}")
        
        # Check in lookup map
        has_edges = tid in tbr._trip_to_stops_map
        print(f"Trip {tid} has transfer edges in lookup map: {has_edges}")
        
        # Check stop sequence
        seq = graph.get_stop_sequence_in_trip(tid, src_stop.id)
        print(f"Trip {tid} sequence for source: {seq}")

if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "NDLS"
    dst = sys.argv[2] if len(sys.argv) > 2 else "HWH"
    asyncio.run(diagnose(src, dst))
