
import asyncio
import logging
import time
from datetime import datetime, date
import sys
import os
from unittest.mock import MagicMock

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastpath-solo-audit")

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.engine import route_engine
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona
from database.session import SessionTransit

async def audit_fastpath():
    print("--- FASTPATH SOLO AUDIT ---")
    
    # 1. Initialize System
    await container.get('db')
    await container.get('search')
    
    db = SessionTransit()
    
    # Use real orchestrator to get initialized router
    orchestrator = UnifiedRoutingOrchestrator(route_engine)
    router = orchestrator.fast_router 
    
    pairs = [
        ("NDLS", "BCT", 5533, 5080),
        ("HWH", "NDLS", 3099, 5533),
        ("SBC", "MAS", 6902, 4736)
    ]
    
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    constraints = RouteConstraints(persona=Persona.STANDARD, max_results=20)
    
    for src_code, dst_code, src_id, dst_id in pairs:
        print(f"\n>>> Testing {src_code} -> {dst_code} (IDs: {src_id} -> {dst_id})")
        try:
            # Ensure graph is ready and linked to router
            graph = await route_engine._get_current_graph(departure_date)
            router.graph = graph
            
            start_ts = time.perf_counter()
            # FastPath find_routes is sync
            routes = router.find_routes(src_id, dst_id, departure_date, constraints)
            latency = (time.perf_counter() - start_ts) * 1000
            
            print(f"Yield: {len(routes)} routes in {latency:.2f}ms")
            if routes:
                print(f"Sample Route JID: {routes[0].journey_id}")
                for i, r in enumerate(routes[:3]):
                    print(f"  [{i}] Engine: {r.metadata.get('engine')}, Segments: {len(r.segments)}, Transfers: {len(r.transfers)}")
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    db.close()

if __name__ == "__main__":
    asyncio.run(audit_fastpath())
