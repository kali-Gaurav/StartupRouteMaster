import asyncio
import os
import sys
import time
from datetime import datetime, date
import logging

# Setup sys.path
sys.path.append(os.getcwd())

# Mute noisy logs
logging.basicConfig(level=logging.ERROR)

async def benchmark_route(source, destination, label, f):
    f.write(f"\n🚀 [BENCHMARK] Testing {label}: {source} -> {destination}\n")
    f.write("-" * 60 + "\n")
    f.flush()
    
    from core.route_engine.engine import RailwayRouteEngine
    from core.route_engine.constraints import RouteConstraints
    from core.route_engine.base import RoutingRequest
    from database.session import SessionTransit
    
    from database.session import initialize_database_pools
    await initialize_database_pools()
    
    engine = RailwayRouteEngine()
    await engine.init()
    
    db = SessionTransit()
    
    # List of engines to test individually
    engines_list = ["HubTier0", "Turbo", "UltraTurbo", "TBR", "RAPTOR", "FastPath"]
    
    results_map = {}
    
    # Use a fixed travel date
    travel_dt = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    for engine_name in engines_list:
        f.write(f"  🔍 Testing Engine: {engine_name}...")
        f.flush()
        
        # FIXED: Remove travel_date from constructor
        c = RouteConstraints()
        c.permitted_engines = [engine_name]

        req = RoutingRequest(
            source_code=source,
            destination_code=destination,
            departure_date=travel_dt,
            constraints=c,
            limit=10,
            db_session=db
        )
        
        start = time.perf_counter()
        try:
            routes = await engine.orchestrator.stream_all_tiers(req)
            lat = (time.perf_counter() - start) * 1000
            count = len(routes)
            min_duration = min([r.total_duration for r in routes]) if routes else 0
            
            results_map[engine_name] = {
                "latency_ms": lat,
                "count": count,
                "min_duration": min_duration,
                "status": "OK"
            }
            f.write(f" DONE ({lat:.1f}ms, {count} routes)\n")
        except Exception as e:
            results_map[engine_name] = {"status": f"ERROR: {str(e)[:50]}", "latency_ms": 0, "count": 0}
            f.write(f" FAILED: {str(e)[:20]}\n")
            import traceback
            traceback.print_exc()
        f.flush()
            
    # Print comparison table
    f.write("\n" + "="*70 + "\n")
    f.write(f"{'Engine':<12} | {'Latency':<10} | {'Found':<6} | {'Best Dur':<10}\n")
    f.write("-" * 70 + "\n")
    for name, data in results_map.items():
        if data["status"] == "OK" and data["latency_ms"] > 0:
            f.write(f"{name:<12} | {data['latency_ms']:>8.2f}ms | {data['count']:>6} | {data['min_duration']:>8} min\n")
        else:
            f.write(f"{name:<12} | {data['status']}\n")
    f.write("="*70 + "\n")
    f.flush()

async def main():
    outfile = "benchmark_results.txt"
    with open(outfile, "w", encoding="utf-8") as f:
        f.write("🚦 STARTING MULTI-ENGINE BENCHMARK\n")
        
        # Test 1: Direct Long
        try:
            await benchmark_route("NDLS", "KOTA", "Direct (Major)", f)
        except Exception as e:
            f.write(f"FATAL1: {e}\n")
            
        # Test 2: Transfer Long
        try:
            await benchmark_route("NDLS", "PGT", "1-Transfer (Long)", f)
        except Exception as e:
            f.write(f"FATAL2: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())
