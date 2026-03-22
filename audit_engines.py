import asyncio
import time
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Setup Logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("engine-audit")

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.engine import route_engine
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona
from database.session import SessionTransit

async def audit_engines():
    print("INITIALIZING ENGINE AUDIT SYSTEM...")
    
    # 1. Initialize IoC ONCE
    await container.get('db')
    await container.get('search') 
    
    db = SessionTransit()
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    constraints = RouteConstraints(persona=Persona.STANDARD, max_results=100)
    
    # 2. Pre-load/Pre-build Graph
    graph = await route_engine._get_current_graph(departure_date)
    orchestrator = UnifiedRoutingOrchestrator(route_engine)
    
    pairs = [
        ("NDLS", "MMCT"),   # Delhi -> Mumbai
        ("MS", "MAS"),     # Chennai
        ("HWH", "NDLS"),   # Howrah -> Delhi
        ("SBC", "MAS"),    # Bangalore -> Chennai
        ("BPL", "RKMP")     # Bhopal
    ]
    
    engines = {
        "UltraTurbo": orchestrator.ultra_turbo,
        "Turbo": orchestrator.turbo_router,
        "TBR": orchestrator.tbr_router, # [Task 27.17]
        "FastPath": orchestrator.fast_router,
        "RAPTOR": orchestrator.raptor
    }
    
    print(f"\n{'Pair':<15} | {'Engine':<12} | {'Yield':<6} | {'Latency':<8} | {'Status'}")
    print("-" * 75)
    
    for src_code, dst_code in pairs:
        from utils.station_utils import resolve_stations
        src_stop, dst_stop = resolve_stations(db, src_code, dst_code)
        if not src_stop or not dst_stop:
            print(f"FAILED to resolve {src_code} or {dst_code}")
            continue

        for name, engine in engines.items():
            start_ts = time.perf_counter()
            found_routes = []
            error = None
            
            try:
                if name == "UltraTurbo":
                    found_routes = await engine.find_routes(src_stop.id, dst_stop.id, departure_date.date(), limit=100)
                elif name == "Turbo":
                    found_routes = engine.find_routes(src_code, dst_code, departure_date, limit=100)
                elif name == "TBR":
                    found_routes = await engine.find_routes(src_stop.id, dst_stop.id, departure_date, constraints, graph)
                elif name == "FastPath":
                    engine.graph = graph
                    found_routes = engine.find_routes(src_stop.id, dst_stop.id, departure_date, constraints)
                elif name == "RAPTOR":
                    found_routes = await engine.find_routes(src_stop.id, dst_stop.id, departure_date, constraints, graph)
            except Exception as e:
                error = f"{type(e).__name__}: {str(e)}"
            
            latency = (time.perf_counter() - start_ts) * 1000
            status = "OK" if not error else f"ERR: {error[:25]}"
            if not error and len(found_routes) == 0:
                status = "ZERO"
                
            print(f"{src_code + '->' + dst_code:<15} | {name:<12} | {len(found_routes):<6} | {latency:7.1f}ms | {status}")

    db.close()
    # 3. Graceful Teardown (Task 27.18)
    await container.shutdown_all()

if __name__ == "__main__":
    asyncio.run(audit_engines())
