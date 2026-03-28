import asyncio
import logging
import json
from datetime import datetime
from core.route_engine.turbo_router import TurboRouter
from core.route_engine.constraints import RouteConstraints
from database.session import initialize_database_pools, SessionTransit
from core.route_engine.engine import route_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_engine")

async def test_turbo():
    await initialize_database_pools()
    router = TurboRouter()
    
    # NDLS (New Delhi) -> BCT (Mumbai Central)
    # Using IDs (Common IDs for these stations)
    # NDLS is usually ID 1, BCT/BCT is around 400
    # I'll use codes instead if the router supports it
    
    # Wait, TurboRouter.find_routes expects IDs.
    # I'll fetch IDs from codes.
    db = SessionTransit()
    from sqlalchemy import text
    src = db.execute(text("SELECT id FROM stops WHERE code = 'NDLS'")).fetchone()
    dst = db.execute(text("SELECT id FROM stops WHERE code = 'BCT'")).fetchone()
    
    if not src or not dst:
        logger.error(f"Station IDs not found for codes. Found: src={src}, dst={dst}")
        return

    src_id, dst_id = src[0], dst[0]
    logger.info(f"Test Search: NDLS({src_id}) -> BCT({dst_id})")
    
    constraints = RouteConstraints(max_transfers=2)
    start_time = datetime(2026, 3, 28, 10, 0)
    
    # Initialize Graph
    graph = await route_engine.get_graph(start_time)
    
    routes = await router.find_routes(src_id, dst_id, start_time, constraints, graph=graph)
    
    logger.info(f"Found {len(routes)} routes.")
    for i, r in enumerate(routes[:3]):
        logger.info(f"Route {i+1}: {r.segments[0].departure_code} -> {r.segments[-1].arrival_code} | Duration: {r.total_duration}m")
        for seg in r.segments:
            logger.info(f"  - {seg.train_number}: {seg.departure_code} ({seg.departure_time.strftime('%H:%M')}) -> {seg.arrival_code} ({seg.arrival_time.strftime('%H:%M')})")

if __name__ == "__main__":
    asyncio.run(test_turbo())
