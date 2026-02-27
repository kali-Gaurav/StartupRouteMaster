import asyncio
import logging
from datetime import datetime, timedelta
from database.session import SessionLocal
from services.station_service import StationService
from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test(engine, src_code, dest_code, target_date, max_transfers=1):
    logger.info("-" * 40)
    logger.info(f"TESTING: {src_code} -> {dest_code} (max_transfers={max_transfers})")
    constraints = RouteConstraints(max_transfers=max_transfers, max_results=5)
    
    start = datetime.now()
    routes = await engine.search_routes(src_code, dest_code, target_date, constraints=constraints)
    end = datetime.now()
    
    logger.info(f"Found {len(routes)} routes in {(end - start).total_seconds()}s")
    for r in routes:
        logger.info(f"Route: {r.total_duration} mins, {len(r.segments)} segments, {len(r.transfers)} transfers, Score: {r.score:.2f}")
        for i, seg in enumerate(r.segments):
            logger.info(f"  [{i+1}] {seg.train_number} {seg.departure_code} -> {seg.arrival_code} ({seg.departure_time})")
        if r.transfers:
            for i, t in enumerate(r.transfers):
                logger.info(f"  (T{i+1}) At {t.station_name}: wait {t.duration_minutes} mins")
    return routes

async def test_pairs():
    engine = RailwayRouteEngine()
    
    # Target Date: Next Wednesday
    today = datetime.now()
    target_date = today + timedelta(days=(2 - today.weekday()) % 7 + 7)
    target_date = target_date.replace(hour=10, minute=0, second=0, microsecond=0)

    # 1. Direct Pair (Western Railway)
    await run_test(engine, "ABR", "ADI", target_date, max_transfers=0)
    
    # 2. Potential Transfer Pair (Western to South/Central)
    # ABR -> BZA (Vijayawada) - Likely requires transfer at ADI, BRC, or PUNE
    # await run_test(engine, "ABR", "BZA", target_date, max_transfers=2)
    
    # 3. Short Transfer (Same line but different trains)
    # PNU -> ADI
    # await run_test(engine, "PNU", "ADI", target_date, max_transfers=1)

if __name__ == "__main__":
    asyncio.run(test_pairs())
