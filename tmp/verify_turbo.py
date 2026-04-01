import asyncio
import time
from datetime import datetime
from core.route_engine.turbo_router import TurboRouter
from core.route_engine.base import RoutingRequest
from core.route_engine.constraints import RouteConstraints
from database.session import SessionTransit, initialize_database_pools

async def test():
    await initialize_database_pools()
    router = TurboRouter()
    db = SessionTransit()
    
    # NDLS to MMCT
    from utils.station_utils import resolve_stations
    source_stop, dest_stop = await asyncio.to_thread(resolve_stations, db, "NDLS", "MMCT")
    
    from core.route_engine.ultra_turbo import UltraTurboDirectEngine
    ut = UltraTurboDirectEngine()
    from database.session import get_raw_transit_conn
    async with get_raw_transit_conn() as conn:
        src_cluster_ids = await ut._resolve_cluster_ids(conn, "NDLS")
        dst_cluster_ids = await ut._resolve_cluster_ids(conn, "MMCT")

    req = RoutingRequest(
        source_code="NDLS",
        destination_code="MMCT",
        departure_date=datetime(2026, 4, 1),
        constraints=RouteConstraints(discovery_only=True),
        limit=10,
        db_session=db,
        src_cluster_ids=src_cluster_ids,
        dst_cluster_ids=dst_cluster_ids
    )
    
    print("🚀 Starting TurboRouter Search...")
    resp = await router.find_routes(req)
    print(f"✅ Yield: {resp.yield_count}")
    for i, r in enumerate(resp.routes):
        print(f"  [{i}] {r.segments[0].train_number} {r.segments[0].departure_time} -> {r.segments[0].arrival_time}")

if __name__ == "__main__":
    asyncio.run(test())
