import asyncio
import logging
import json
from datetime import datetime, timedelta
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import RoutingRequest, RouteConstraints
from core.route_engine.constraints import DiscoveryModel

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("VYA_Audit")

async def init_nexus():
    from core.nexus.bootstrapper import nexus_boot
    from core.nexus.database.node import database_node
    from core.nexus.cache.node import cache_node
    
    # Register core nodes for DB and Cache
    nexus_boot.register(database_node)
    nexus_boot.register(cache_node)
    
    print("Nexus: Initiating Core Bootstrap...")
    await nexus_boot.bootstrap()
    
    from core.engines.route_engine import init_route_engine
    print("RouteEngine: Initializing...")
    await init_route_engine()
    print("RouteEngine: Ready.")
    
    from core.route_engine.engine import get_route_engine
    engine = get_route_engine()
    print("RailwayRouteEngine: Initializing...")
    await engine.init()
    print("RailwayRouteEngine: Ready.")
    
    print("Nexus: Bootstrap Complete.")

async def audit_search(source, dest, iteration=0):
    from core.route_engine.engine import get_route_engine
    engine = get_route_engine()
    print(f"DEBUG: Engine type is {type(engine)}")
    orchestrator = UnifiedRoutingOrchestrator(engine)
    
    constraints = RouteConstraints(
        discovery_model=DiscoveryModel.OMNISCIENT,
        max_transfers=3,
        preferred_class="3A"
    )
    
    request = RoutingRequest(
        source_code=source,
        destination_code=dest,
        departure_date=datetime.now() + timedelta(days=7),
        limit=100,
        constraints=constraints,
        metadata={"search_iteration": iteration},
        force_refresh=True
    )
    
    print(f"\n{'='*60}")
    print(f"SEARCH: {source} -> {dest} (Iteration: {iteration})")
    print(f"{'='*60}")
    
    start_time = datetime.now()
    results = await orchestrator.stream_all_tiers(request)
    duration = (datetime.now() - start_time).total_seconds()
    
    buckets = results.get("buckets", {})
    
    print(f"\nBUCKET YIELDS:")
    print(f"  - Direct:         {len(buckets.get('direct', [])):>2}")
    print(f"  - 1-Transfer:     {len(buckets.get('one_transfer', [])):>2}  (Target: 15+)")
    print(f"  - 2-Transfer:     {len(buckets.get('two_transfer', [])):>2}  (Target: 10+)")
    print(f"  - 3-Transfer:     {len(buckets.get('three_transfer', [])):>2}  (Target: 10+)")
    print(f"  - Advanced:       {len(buckets.get('advanced', [])):>2}")
    
    print(f"\nTELEMETRY:")
    print(f"  - Latency:        {duration:.2f}s")
    metadata = results.get("metadata", {})
    print(f"  - Total Visible:  {metadata.get('visible_yield', 0)}")
    print(f"  - RapidAPI Calls: {metadata.get('rapid_api_count', 'N/A')}")
    
    # Check for Redistribution Options
    redist = results.get("redistribution_options", [])
    if redist:
        print(f"\nREDISTRIBUTION VALVES: {len(redist)} found")
        for i, opt in enumerate(redist[:2]):
            print(f"  [{i+1}] {opt.ui_display_text} (Benefit: {opt.system_benefit_score})")

    return results

async def main():
    # Initialize Nexus Core
    await init_nexus()
    
    # Test a major corridor
    await audit_search("BCT", "NDLS", iteration=0)
    
    # Test Load More (Iteration 1)
    # await audit_search("BCT", "NDLS", iteration=1)

if __name__ == "__main__":
    asyncio.run(main())
