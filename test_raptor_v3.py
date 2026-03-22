
import asyncio
import logging
from datetime import datetime, timedelta
import sys
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-raptor-v3")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.engine import route_engine
from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona
from database.session import SessionTransit

async def test_raptor():
    await container.get('db')
    await container.get('search')
    
    db = SessionTransit()
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    constraints = RouteConstraints(persona=Persona.STANDARD, max_results=50, range_minutes=1440)
    router = OptimizedRAPTOR(max_transfers=3)
    
    # 5533=NDLS, 5080=BCT
    src_id, dst_id = 5533, 5080
    
    print(f"Testing NDLS -> BCT (IDs: {src_id} -> {dst_id})")
    try:
        graph = await route_engine._get_current_graph(departure_date)
        routes = await router.find_routes(src_id, dst_id, departure_date, constraints, graph)
        print(f"Yield: {len(routes)} routes")
        for i, r in enumerate(routes[:5]):
            print(f"  [{i}] Segments: {len(r.segments)}, Transfers: {len(r.transfers)}, Time: {r.total_duration}m, JID: {r.journey_id}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
    db.close()

if __name__ == "__main__":
    asyncio.run(test_raptor())
