
import asyncio
import logging
from datetime import datetime, date
import sys
import os

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("turbo-solo-audit")

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.turbo_router import TurboRouter
from utils.station_utils import resolve_stations
from database.session import SessionTransit

async def audit_turbo():
    print("--- TURBO SOLO AUDIT ---")
    
    # 1. Initialize DB
    await container.get('db')
    db = SessionTransit()
    
    router = TurboRouter()
    
    # Test cases
    pairs = [
        ("NDLS", "BCT"),   # Long (Expected Direct or 1-T)
        ("MS", "MAS"),     # Short
        ("BPL", "RKMP")    # Very Short
    ]
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    
    for src_code, dst_code in pairs:
        print(f"\n>>> Testing {src_code} -> {dst_code}")
        try:
            start_ts = time.perf_counter()
            # Turbo find_routes is synchronous but we might wrap it in thread later
            routes = router.find_routes(src_code, dst_code, departure_date, limit=20)
            latency = (time.perf_counter() - start_ts) * 1000
            print(f"Yield: {len(routes)} routes in {latency:.2f}ms")
            
            if len(routes) > 0:
                print(f"Sample Route: {routes[0]['type']} via {routes[0].get('hub', 'DIRECT')}")
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    db.close()

if __name__ == "__main__":
    import time
    asyncio.run(audit_turbo())
