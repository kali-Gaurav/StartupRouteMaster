
import sys
from pathlib import Path
backend_path = str(Path(__file__).resolve().parent.parent.parent.parent.parent / "backend")
if backend_path not in sys.path:
    sys.path.append(backend_path)
    # Also add the root for 'backend.xxx' style imports
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent.parent))

import asyncio
import time
import logging
from sqlalchemy import text
from backend.database.session import SessionTransit
from backend.services.search_service import SearchService
from backend.database.models import StationRealtimeHeartbeat
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("forge.heartbeat_storm")

async def setup_test_data():
    """Warms up the hub."""
    async with SessionTransit() as db:
        # Create a fresh heartbeat for NDLS
        hb = db.query(StationRealtimeHeartbeat).filter_by(station_code="NDLS").first()
        if not hb:
            hb = StationRealtimeHeartbeat(
                station_code="NDLS",
                status_summary="10 trains delayed",
                trains_json=[{"train_no": "12301", "status": "DELAYED", "delay": 45}],
                sync_latency_ms=100,
                last_updated_at=datetime.utcnow(),
                last_updated_unix=int(time.time()),
                expires_at=datetime.utcnow() + timedelta(minutes=30)
            )
            db.add(hb)
        else:
            hb.expires_at = datetime.utcnow() + timedelta(minutes=30)
            hb.last_updated_unix = int(time.time())
        db.commit()
    logger.info("✅ Test Data Pre-Warmed [NDLS].")

async def simulate_search_load(total_requests: int = 100):
    """Simulates a massive search flood."""
    logger.info(f"🔨 Starting Heartbeat Storm: {total_requests} Search Requests...")
    
    start_all = time.perf_counter()
    
    async def single_search():
        async with SessionTransit() as db:
            svc = SearchService(db)
            # Search NDLS -> AGC (Agra)
            # We use explain_zero_results or search_routes (mocked)
            # But the Orchestrator check is the key
            res = await svc.route_engine.find_routes_direct(
                source_code="NDLS", 
                dest_code="AGC",
                departure_date=datetime.now()
            )
            return len(res)

    # Note: We run them in batches to not kill the SQLite/Postgres connection pool
    batch_size = 20
    results = []
    for i in range(0, total_requests, batch_size):
        batch = [single_search() for _ in range(batch_size)]
        res = await asyncio.gather(*batch)
        results.extend(res)
    
    duration = time.perf_counter() - start_all
    logger.info(f"🏁 Storm Complete! Duration: {duration:.2f}s | Avg Latency: {(duration/total_requests)*1000:.2f}ms")
    return results

async def main():
    await setup_test_data()
    await simulate_search_load(100) # Start with 100 on local test

if __name__ == "__main__":
    asyncio.run(main())
