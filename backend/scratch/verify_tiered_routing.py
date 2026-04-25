
import asyncio
import logging
from datetime import datetime
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine import get_route_engine
from core.route_engine.base import RoutingRequest
from core.route_engine.constraints_engine import ConstraintsEngine
from core.route_engine.constraints import DiscoveryModel
from database.session import SessionTransit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TieredVerify")

async def test_tiered_workflow():
    from database.session import initialize_database_pools
    await initialize_database_pools()
    
    db = SessionTransit()
    engine = get_route_engine()
    orchestrator = UnifiedRoutingOrchestrator(engine)
    
    source = "NDLS"
    dest = "BCT"
    date = datetime(2026, 5, 20)
    
    tiers = [
        DiscoveryModel.BACKBONE,
        DiscoveryModel.MULTIMODAL,
        DiscoveryModel.OMNISCIENT
    ]
    
    for tier in tiers:
        print(f"\n--- TESTING TIER: {tier.name} ---")
        
        # 1. Initialize Constraints for Tier
        constraints = ConstraintsEngine.initialize_constraints(
            persona_str="comfort",
            travel_date=date.date(),
            discovery_model=tier
        )
        
        # 2. Build Request
        request = RoutingRequest(
            source_code=source,
            destination_code=dest,
            departure_date=date,
            constraints=constraints,
            limit=5,
            db_session=db
        )
        
        # 3. Execute Search
        print(f"Executing search for {source} -> {dest} (Model: {tier.name})...")
        start = datetime.now()
        routes = await orchestrator.search_all_tiers(request)
        end = datetime.now()
        
        print(f"Found {len(routes)} routes in {(end-start).total_seconds():.2f}s")
        
        if routes:
            top = routes[0]
            print(f"Top Route Score: {top.score:.2f}")
            print(f"Engine used: {top.metadata.get('engine', 'unknown')}")
            print(f"Fares verified: {'live_availability' in top.segments[0].metadata}")
            print(f"FOMO Active: {top.metadata.get('has_high_fomo', False)}")
            
            # Tier-Specific Assertions (Visual Check)
            if tier == DiscoveryModel.BACKBONE:
                if any("multimodal" in r.metadata.get("engine", "") for r in routes):
                    print("ERROR: Multimodal engine leaked into Backbone tier!")
            elif tier == DiscoveryModel.OMNISCIENT:
                if top.metadata.get("has_high_fomo"):
                    print("SUCCESS: Psychological Intelligence (FOMO) detected in Omniscient tier.")

    db.close()

if __name__ == "__main__":
    asyncio.run(test_tiered_workflow())
