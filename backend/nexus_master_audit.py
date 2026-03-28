import asyncio
import time
import os
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Import Nexus Core
from database.session import SessionTransit, initialize_database_pools
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona, Route
from core.nexus.audit.governor import nexus_governor

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("nexus-audit")

async def run_detailed_audit():
    print("\n" + "#"*80)
    print("      🛡️  NEXUS MASTER ENGINE AUDIT & PERFORMANCE BENCHMARK (V3-Fiber)      ")
    print("█"*80 + "\n")

    # 1. Initialize Nexus Persistence & Fabric
    logger.info("Initializing Nexus Infrastructure...")
    start_init = time.perf_counter()
    await initialize_database_pools()
    db = SessionTransit()
    engine = RailwayRouteEngine()
    orchestrator = UnifiedRoutingOrchestrator(engine)
    init_lat = (time.perf_counter() - start_init) * 1000
    
    # 2. Nexus Resource Governor Status Check
    gov_stats = await nexus_governor.get_stats()
    print(f"📋 [GOVERNOR] CPU: {gov_stats['cpu_percent']}% | RAM: {gov_stats['ram_percent']}% | Throttle: {gov_stats['throttle_factor']}")
    print(f"⚙️ [FABRIC] JIT Initialized in {init_lat:.2f}ms\n")

    # 3. Test Cases (Diverse Topology)
    test_cases = [
        {"src": "KYN", "dst": "TNA", "name": "Kalyan -> Thane (High Density Sub-Urban)"},
        {"src": "ET", "dst": "BINA", "name": "Itarsi -> Bina (Main Line)"},
        {"src": "MAS", "dst": "SBC", "name": "Chennai -> Bangalore (Inter-City)"}
    ]

    date = datetime.now() + timedelta(days=2)
    default_constraints = RouteConstraints(max_transfers=2, persona=Persona.BUDGET)

    # Prepare Graph (Nexus Time-Dependent)
    graph = await engine._get_current_graph(date)

    # Individual Engine Audit
    # We'll call the internal orchestrator methods to isolate engines
    engines_to_test = [
        ("Tier 0: Hub Backbone", lambda s, d, g: orchestrator._search_tier_0_hubs_async(s.id, d.id, date, db)),
        ("Tier 1: Turbo Direct", lambda s, d, g: orchestrator.turbo_router.find_routes(s.code, d.code, date, 50)),
        ("Tier 2: Trip-Based (TBR)", lambda s, d, g: orchestrator.tbr_router.find_routes([s.id], [d.id], date, default_constraints, g)),
        ("Tier 3: RAPTOR (Discovery)", lambda s, d, g: orchestrator.raptor.find_routes([s.id], [d.id], date, default_constraints, g))
    ]

    from utils.station_utils import resolve_stations

    for tc in test_cases:
        print(f"🔍 [AUDIT] Testing Route: {tc['name']} ({tc['src']} -> {tc['dst']})")
        
        # Resolve target IDs
        src_stop, dst_stop = await asyncio.to_thread(resolve_stations, db, tc['src'], tc['dst'])
        if not src_stop or not dst_stop:
            logger.error(f"  ❌ Failed to resolve stations for {tc['src']}->{tc['dst']}")
            continue

        # Prepare Graph (Nexus Time-Dependent)
        graph = await engine._get_current_graph(date)

        for engine_name, search_fn in engines_to_test:
            start_e = time.perf_counter()
            try:
                res = await search_fn(src_stop, dst_stop, graph)
                
                lat = (time.perf_counter() - start_e) * 1000
                count = len(res)
                status = "✅ OK" if count > 0 else "⚠️  EMPTY (Valid for some engines)"
                print(f"  ├─ {engine_name:<25}: {lat:>8.2f}ms | Yield: {count:<3} | Status: {status}")
                
                # Check for "Nexus Hydration" (Metadata presence)
                if count > 0:
                    sample = res[0]
                    has_engine_tag = "engine" in sample.metadata if hasattr(sample, "metadata") else True # Dicts might differ
                    has_pricing = sample.total_cost > 0 if isinstance(sample, Route) else True
                    if not has_engine_tag: logger.warning(f"    └─ Missing Nexus Engine Tagging!")
                    if not has_pricing: logger.warning(f"    └─ Pricing Fabric NOT hydrated for this tier.")

            except Exception as e:
                logger.error(f"  ├─ {engine_name:<25}: FAILED | Error: {e}")

        print("  " + "─"*50)

    # 4. Nexus Full Orchestration Stress Test
    print("\n🚀 [STRESS] Running Full Streamed Orchestration (All-Tiers Enabled)...")
    start_full = time.perf_counter()
    routes_batch = []
    async for batch in orchestrator.stream_all_tiers(test_cases[0]["src"], test_cases[0]["dst"], date, default_constraints, db=db):
        routes_batch.extend(batch)
    
    full_lat = (time.perf_counter() - start_full) * 1000
    print(f"✨ [ORCHESTRATOR] Total Result Set: {len(routes_batch)} routes | Stream-to-Complete: {full_lat:.2f}ms")

    # 5. Nexus L2 Cache Verification
    try:
        from core.nexus.cache.node import cache_node
        from services.multi_layer_cache import multi_layer_cache
        redis_ok = multi_layer_cache.redis is not None
        print(f"\n⚡ [CACHE] Redis L2 Connectivity: {'✅ ACTIVE' if redis_ok else '❌ OFFLINE'}")
        if redis_ok:
            test_key = "nexus:audit:heartbeat"
            await multi_layer_cache.put(test_key, "alive", ttl=10)
            val = await multi_layer_cache.get(test_key)
            print(f"⚡ [CACHE] L2 Read/Write Test: {'✅ SUCCESS' if val == 'alive' else '❌ FAILED'}")
    except Exception as e:
        print(f"⚡ [CACHE] Nexus L2 Error: {e}")

    print("\n" + "#"*80)
    print("                            AUDIT COMPLETE                                  ")
    print("█"*80 + "\n")
    db.close()

if __name__ == "__main__":
    asyncio.run(run_detailed_audit())
