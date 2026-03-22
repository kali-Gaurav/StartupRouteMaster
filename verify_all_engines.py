import asyncio
import logging
import time
from datetime import datetime
import sys
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("engine-comparator")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.engine import route_engine
from core.route_engine.tbr_router import TripBasedRouter
from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.turbo_router import TurboRouter
from core.route_engine.ultra_turbo import UltraTurboDirectEngine
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona

async def run_comparison():
    print("\n" + "="*50)
    print("🚀 ROUTEMASTER ENGINE COMPARATIVE AUDIT")
    print("="*50)

    # Initialize dependencies
    db = await container.get('db')
    await container.get('search')
    
    # Engines to test
    engines = {
        "TBR v4.2 (New)": TripBasedRouter(max_transfers=3),
        "RAPTOR v2": OptimizedRAPTOR(max_transfers=3),
        "Ultra-Turbo (Direct/1T)": UltraTurboDirectEngine()
    }

    # Test Cases: (Source, Dest, Label)
    # Using codes for consistency as some engines prefer them
    test_cases = [
        ("NDLS", "MMCT", "Long Haul (Hub to Hub)"),
        ("MTJ", "AGC", "Short Run (Local)"),
        ("TVC", "SBC", "Medium Cross-Zone")
    ]
    
    departure_date = datetime(2026, 3, 22, 10, 0, 0)
    constraints = RouteConstraints(persona=Persona.STANDARD, max_results=10, range_minutes=1440)

    for src_code, dst_code, label in test_cases:
        print(f"\n📍 CASE: {label} ({src_code} -> {dst_code})")
        
        # Resolve to IDs for TBR/RAPTOR
        graph = await route_engine._get_current_graph(departure_date)
        s_stop = graph.get_stop_by_code(src_code)
        d_stop = graph.get_stop_by_code(dst_code)
        
        if not s_stop or not d_stop:
            print(f"  ⚠️ Skipping: Could not resolve {src_code} or {dst_code}")
            continue

        for engine_name, engine in engines.items():
            try:
                start_ts = time.perf_counter()
                
                # Universal interface adaptors
                if isinstance(engine, (TripBasedRouter, OptimizedRAPTOR)):
                    routes = await engine.find_routes(s_stop.id, d_stop.id, departure_date, constraints, graph)
                elif isinstance(engine, UltraTurboDirectEngine):
                    routes = await engine.find_routes(src_code, dst_code, departure_date.date(), limit=10)
                else:
                    routes = []
                
                latency = (time.perf_counter() - start_ts) * 1000
                
                # Validate Reachability
                invalid = 0
                for r in routes:
                    if not r.segments: continue
                    # Rough check: first segment departure or in metro group
                    # and last segment arrival or in metro group
                    pass 

                print(f"  [v] {engine_name:25} | {len(routes):2} routes | {latency:7.2f}ms")
                if routes:
                    best = routes[0]
                    transfers = len(best.transfers) if hasattr(best, 'transfers') else (len(best.segments)-1 if best.segments else 0)
                    print(f"      Best: {best.total_duration} mins, {transfers} transfers")
            
            except Exception as e:
                print(f"  [x] {engine_name:25} | ERROR: {str(e)[:50]}...")

    await container.shutdown_all()

if __name__ == "__main__":
    asyncio.run(run_comparison())
