import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionTransit
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.constraints import RouteConstraints
from core.route_engine import route_engine
from utils.station_utils import resolve_stations

async def test_search():
    logging.basicConfig(level=logging.INFO)
    
    # Task 11 compatibility: Manually trigger JIT foundation
    from services.jit_manager import jit_manager
    from app import load_database, load_cache, load_route_engine
    
    print("⏳ Initializing JIT Foundation...")
    jit_manager.register_node("DATABASE", [], load_database)
    jit_manager.register_node("CACHE", [], load_cache)
    jit_manager.register_node("GRAPH", ["DATABASE", "CACHE"], load_route_engine)
    
    print("⏳ Triggering DATABASE...")
    await jit_manager.ensure_ready("DATABASE")
    print("⏳ Triggering CACHE...")
    await jit_manager.ensure_ready("CACHE")
    print("⏳ Triggering GRAPH...")
    await jit_manager.ensure_ready("GRAPH")
    
    print("✅ JIT Foundation Ready.")
    db = SessionTransit()
    
    source = "NDLS"
    dest = "BCT" # Mumbai Central
    travel_date = datetime.now() + timedelta(days=7)
    
    print(f"🔍 TESTING SEARCH: {source} -> {dest} on {travel_date.date()}")
    
    # 1. Resolve Stations
    src_stop, dst_stop = resolve_stations(db, source, dest)
    if not src_stop or not dst_stop:
        print(f"❌ FAILED to resolve stations: src={src_stop}, dst={dst_stop}")
        return

    print(f"✅ Resolved: {src_stop.name} ({src_stop.id}) -> {dst_stop.name} ({dst_stop.id})")

    # 2. Test Tier 0: Hubs
    orchestrator = UnifiedRoutingOrchestrator(route_engine)
    print("\n--- Testing Tier 0 (Hubs) ---")
    hub_results = orchestrator._search_tier_0_hubs(src_stop.id, dst_stop.id, travel_date, db)
    print(f"Found {len(hub_results)} hub results.")
    for r in hub_results:
        print(f"  - Route: {[s.train_number for s in r.segments]}")

    # 3. Test Full Search
    print("\n--- Testing Full Orchestrated Search ---")
    constraints = RouteConstraints(travel_date=travel_date.date())
    results = await orchestrator.search_all_tiers(source, dest, travel_date, constraints, limit=10, db=db)
    
    print(f"Found {len(results)} total results.")
    for i, r in enumerate(results):
        print(f"Result {i+1}:")
        print(f"  - Engine: {r.metadata.get('engine')}")
        print(f"  - Segments: {[(s.departure_code, s.arrival_code, s.train_number) for s in r.segments]}")
        print(f"  - Transfers: {[t.station_name for t in r.transfers]}")

    db.close()

if __name__ == "__main__":
    asyncio.run(test_search())
