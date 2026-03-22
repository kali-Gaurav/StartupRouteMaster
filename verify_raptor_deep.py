
import asyncio
import logging
import time
from datetime import datetime
import sys
import os

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("raptor-deep-audit")

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona
from database.session import SessionTransit

async def audit_raptor_deep():
    print("--- RAPTOR ENGINE DEEP AUDIT ---")
    
    await container.get('db')
    await container.get('search')
    
    db = SessionTransit()
    from core.route_engine.engine import route_engine
    
    # Test cases mirroring Turbo
    pairs = [
        ("NDLS", "MMCT", 5533, 5080), 
        ("MS", "MAS", 5265, 4736),
        ("SBC", "MAS", 6902, 4736)
    ]
    
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    # Aggressive constraints for max yield
    constraints = RouteConstraints(
        persona=Persona.STANDARD, 
        max_results=100, 
        range_minutes=1440,
        timeout_ms=15000 # 15s for deep discovery
    )
    
    router = OptimizedRAPTOR(max_transfers=3)
    
    for src_code, dst_code, src_id, dst_id in pairs:
        print(f"\n>>> Testing {src_code} -> {dst_code}")
        try:
            graph = await route_engine._get_current_graph(departure_date)
            
            start_ts = time.perf_counter()
            routes = await router.find_routes(src_id, dst_id, departure_date, constraints, graph)
            latency = (time.perf_counter() - start_ts) * 1000
            
            print(f"Yield: {len(routes)} routes in {latency:.2f}ms")
            for i, r in enumerate(routes[:3]):
                print(f"  [{i}] Segments: {len(r.segments)}, Transfers: {len(r.transfers)}, Time: {r.total_duration}m, JID: {r.journey_id[:50]}...")
        except Exception as e:
            print(f"ERROR: {e}")

    db.close()
    await container.shutdown_all()

if __name__ == "__main__":
    asyncio.run(audit_raptor_deep())
