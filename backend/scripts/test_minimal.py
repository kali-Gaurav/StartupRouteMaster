import asyncio
import logging
from datetime import datetime, date
from database.session import SessionLocal
from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
from database.models import Stop

async def test_minimal():
    engine = RailwayRouteEngine()
    db = SessionLocal()
    
    # 2026-03-11 is a Wednesday
    d = datetime(2026, 3, 11, 10, 0, 0)
    
    logger = logging.getLogger("TestMinimal")
    logger.setLevel(logging.DEBUG)
    
    # 1. Check if engine sees the stops
    abr = db.query(Stop).filter(Stop.stop_id == 'ABR').first()
    adi = db.query(Stop).filter(Stop.stop_id == 'ADI').first()
    print(f"ABR: {abr.id}, ADI: {adi.id}")

    # 2. Build graph
    graph = await engine._get_current_graph(d)
    print(f"Graph Built: {len(graph.stop_cache)} stops, {len(graph.trip_segments)} trips")
    
    # 3. Check departures from ABR
    deps = graph.get_departures_from_stop(abr.id, d)
    print(f"Departures from ABR: {len(deps)}")
    
    # 4. Search
    constraints = RouteConstraints(max_transfers=0)
    routes = await engine.raptor.find_routes(abr.id, adi.id, d, constraints, graph=graph)
    print(f"Routes Found: {len(routes)}")
    for r in routes:
        print(f"Route: {r.total_duration} mins, {len(r.segments)} segments")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(test_minimal())
