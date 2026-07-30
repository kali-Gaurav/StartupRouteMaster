import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# [Task 117.9] Link backend module base index
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.append(str(_root))

from core.route_engine.engine import get_route_engine
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import RoutingRequest
from core.route_engine.constraints_engine import ConstraintsEngine
from database.session import SessionTransit, initialize_database_pools, SessionLocal
from services.agents.demand_forecasting_agent import DemandForecastingAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("predictive_jit")

async def execute_predictive_hydration():
    """
    [Task 12.5] Predictive JIT Hydration Sequence.
    Ensures top-tier station pairs have warm caches and hydrated live data.
    """
    logger.info("🚀 Starting Predictive JIT Hydration Sequence...")
    await initialize_database_pools()
    
    from database.session import init_db
    await init_db()
    
    engine = get_route_engine()
    orchestrator = UnifiedRoutingOrchestrator(engine)
    db_transit = SessionTransit()
    db_user = SessionLocal()
    
    try:
        # 1. Fetch Top-Tier Targets
        agent = DemandForecastingAgent(db_user)
        targets = await agent.get_prioritized_warmup_targets()
        
        # Limit to top 50 for JIT sequence
        jit_targets = targets[:50]
        logger.info(f"Found {len(jit_targets)} high-demand corridors for hydration.")
        
        # 2. Sequential Hydration (to avoid overwhelming resources)
        travel_date = datetime.now() + timedelta(days=1) # Focus on tomorrow
        
        for i, (src, dst) in enumerate(jit_targets):
            logger.info(f"[{i+1}/50] Hydrating corridor: {src} -> {dst}")
            
            try:
                constraints = ConstraintsEngine.initialize_constraints(
                    persona_str="comfort",
                    travel_date=travel_date.date(),
                    quota="GN"
                )
                
                request = RoutingRequest(
                    source_code=src,
                    destination_code=dst,
                    departure_date=travel_date,
                    constraints=constraints,
                    db_session=db_transit,
                    force_refresh=True # Ensure we actually run the engine and hydrate
                )
                
                # Running search_all_tiers triggers the full hydration pipeline
                await orchestrator.search_all_tiers(request)
                
                logger.info(f"✅ Successfully hydrated {src} -> {dst}")
                
                # Small cool-down to keep P95 latency stable for active users
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Failed to hydrate {src} -> {dst}: {e}")
                
    finally:
        db_transit.close()
        db_user.close()
        logger.info("🏁 Predictive JIT Hydration Sequence Completed.")

if __name__ == "__main__":
    asyncio.run(execute_predictive_hydration())
