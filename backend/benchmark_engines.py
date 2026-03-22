import asyncio
import time
import os
import psutil
import tracemalloc
from datetime import datetime, timedelta
import logging

from database.session import SessionTransit, initialize_database_pools
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("benchmark")

def get_memory():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # MB

async def run_benchmark():
    logger.info("Initializing Backend Engine...")
    await initialize_database_pools()
    db = SessionTransit()
    engine = RailwayRouteEngine()
    orchestrator = UnifiedRoutingOrchestrator(engine)

    # Test cases: High connectivity vs Low connectivity
    test_cases = [
        {"src": "NDLS", "dst": "CSMT", "desc": "High Connectivity (Delhi -> Mumbai)"},
        {"src": "PGT", "dst": "KOTA", "desc": "Low Connectivity (Palakkad -> Kota)"},
        {"src": "GHY", "dst": "BNC", "desc": "Extreme Distance (Guwahati -> Bangalore)"}
    ]

    date = datetime.now() + timedelta(days=2)
    
    print("\n" + "="*60)
    print("ROUTE ENGINE PROFILING & BOTTLENECK ANALYSIS")
    print("="*60)

    for tc in test_cases:
        print(f"\n[Test Case] {tc['desc']} ({tc['src']} -> {tc['dst']})")
        
        # Test 1: Strict Constraints (Budget, max 2 transfers, strict layover)
        constraints_strict = RouteConstraints(
            max_transfers=2,
            min_transfer_time=45,
            max_layover_time=360,
            persona=Persona.BUDGET
        )
        
        # Test 2: Relaxed Constraints (Comfort, max 4 transfers, relaxed layover)
        constraints_relaxed = RouteConstraints(
            max_transfers=4,
            min_transfer_time=30,
            max_layover_time=720,
            persona=Persona.COMFORT
        )

        for name, c in [("Strict Constraints", constraints_strict), ("Relaxed Constraints", constraints_relaxed)]:
            tracemalloc.start()
            start_mem = get_memory()
            start_time = time.perf_counter()
            
            try:
                # Running the orchestrator (which runs all engines internally)
                routes = await orchestrator.search_all_tiers(
                    source_code=tc["src"],
                    destination_code=tc["dst"],
                    departure_date=date,
                    constraints=c,
                    limit=100,
                    db=db
                )
                
                exec_time = (time.perf_counter() - start_time) * 1000
                end_mem = get_memory()
                current, peak = tracemalloc.get_traced_memory()
                
                print(f"  + {name}:")
                print(f"    + Yield: {len(routes)} routes found")
                print(f"    + Latency: {exec_time:.2f} ms")
                print(f"    + Memory Spike: {(peak / 1024 / 1024):.2f} MB")
                
            except Exception as e:
                print(f"  + {name} FAILED: {str(e)}")
            finally:
                tracemalloc.stop()

    db.close()
    print("\n" + "="*60)
    print("✅ PROFILING COMPLETE")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
