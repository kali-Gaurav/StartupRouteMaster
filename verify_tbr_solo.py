import asyncio
import logging
import time
from datetime import datetime
import sys
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("tbr-solo-audit")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.engine import route_engine
from core.route_engine.tbr_router import TripBasedRouter
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona
from database.session import SessionTransit

async def audit_tbr():
    print("--- TBR SOLO DEEP AUDIT ---")
    
    await container.get('db')
    await container.get('search')
    
    db = SessionTransit()
    
    # NDLS -> MMCT (Long Haul, requires multiple transfers usually if not direct)
    src_id, dst_id = 5533, 5080 
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    constraints = RouteConstraints(persona=Persona.STANDARD, max_results=50, range_minutes=1440)
    
    router = TripBasedRouter(max_transfers=3)
    
    print(f"Testing NDLS -> MMCT (IDs: {src_id} -> {dst_id})")
    try:
        graph = await route_engine._get_current_graph(departure_date)
        
        # 1. Inspect the Snapshot Data
        snap = graph.snapshot
        print(f"Snapshot Loaded: {snap is not None}")
        if snap:
            print(f"TBR Nodes Loaded: {snap.tbr_trip_nodes is not None}")
            print(f"TBR Trip Index Keys: {len(snap.tbr_trip_index)}")
            print(f"TBR Stop Index Keys: {len(snap.tbr_stop_index)}")
        
        # 2. Inspect the Router Data
        print(f"Router Edges Loaded: {router._edges is not None}")
        if router._edges is not None:
            print(f"Router Edges Count: {len(router._edges)}")
            print(f"Router Edge Index Keys: {len(router._edge_index)}")

        start_ts = time.perf_counter()
        routes = await router.find_routes(src_id, dst_id, departure_date, constraints, graph)
        latency = (time.perf_counter() - start_ts) * 1000
        
        print(f"\nYield: {len(routes)} routes in {latency:.2f}ms")
        
        # [Task 27.18] Filter for multi-transfer routes to verify discovery
        transfer_routes = [r for r in routes if len(r.transfers) > 0]
        print(f"Multi-transfer routes discovered: {len(transfer_routes)}")
        
        display_list = transfer_routes[:3] + [r for r in routes if len(r.transfers) == 0][:2]
        
        for i, r in enumerate(display_list):
            print(f"  [{i}] Segments: {len(r.segments)}, Transfers: {len(r.transfers)}, Time: {r.total_duration}m")
            for j, s in enumerate(r.segments):
                print(f"      Seg {j}: {s.departure_stop_id} -> {s.arrival_stop_id} (Trip {s.trip_id})")
                
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    db.close()
    await container.shutdown_all()

if __name__ == "__main__":
    asyncio.run(audit_tbr())
