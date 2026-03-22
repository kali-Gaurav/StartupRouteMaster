
import asyncio
import logging
import time
from datetime import datetime, date
import sys
import os

# Setup Logging
logging.basicConfig(level=logging.DEBUG) # Use DEBUG for raptor internals
logger = logging.getLogger("raptor-solo-audit")

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.engine import route_engine
from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona
from database.session import SessionTransit

async def audit_raptor():
    print("--- RAPTOR SOLO AUDIT ---")
    
    # 1. Initialize System
    await container.get('db')
    await container.get('search')
    
    db = SessionTransit()
    
    # Test cases
    pairs = [
        ("NDLS", "BCT", 5533, 5080), # Long
        ("SBC", "MAS", 6902, 4736)  # Medium
    ]
    
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    # Standard constraints
    constraints = RouteConstraints(
        persona=Persona.STANDARD, 
        max_results=50,
        range_minutes=1440 # 24h window
    )
    
    router = OptimizedRAPTOR(max_transfers=3)
    
    for src_code, dst_code, src_id, dst_id in pairs:
        print(f"\n>>> Testing {src_code} -> {dst_code} (IDs: {src_id} -> {dst_id})")
        try:
            # Ensure graph is ready
            graph = await route_engine._get_current_graph(departure_date)
            
            # Audit Step 1: Check pattern departures from source
            patterns = graph.get_pattern_departures(src_id, departure_date, lookahead_minutes=1440)
            print(f"  Patterns found at source: {len(patterns)}")
            total_deps = sum(len(v) for v in patterns.values())
            print(f"  Total trip departures in window: {total_deps}")
            
            start_ts = time.perf_counter()
            routes = await router.find_routes(src_id, dst_id, departure_date, constraints, graph)
            latency = (time.perf_counter() - start_ts) * 1000
            
            print(f"Yield: {len(routes)} routes in {latency:.2f}ms")
            
            if len(routes) > 0:
                print(f"Sample Route JID: {routes[0].journey_id}")
                for i, r in enumerate(routes[:3]):
                    print(f"  [{i}] Engine: {r.metadata.get('engine')}, Segments: {len(r.segments)}, Transfers: {len(r.transfers)}")
            else:
                # Deep Diagnostic
                print("  DIAGNOSTIC: Checking if destination is reachable in bitsets...")
                reachable_count = 0
                for pid, deps in patterns.items():
                    for dt, tid in deps:
                        if graph.can_reach_destination(tid, dst_id):
                            reachable_count += 1
                print(f"  Trips passing bitset reachability to {dst_code}: {reachable_count}")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    db.close()

if __name__ == "__main__":
    asyncio.run(audit_raptor())
