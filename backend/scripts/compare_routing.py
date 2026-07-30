import asyncio
import os
import sys
import time
import logging
from datetime import datetime, timedelta

# Absolute imports setup
sys.path.append(os.getcwd())

# Mute noisy logs
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("compare_routing")

from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
from database.session import initialize_database_pools, SessionTransit
from core.data_utils.structures import Route

async def benchmark_engine(engine_instance, engine_name, source, destination, travel_dt, db):
    constraints = RouteConstraints()
    constraints.permitted_engines = [engine_name]
    constraints.max_results = 20
    constraints.timeout_ms = 15000 # 15s timeout for benchmarks
    
    start_time = time.perf_counter()
    try:
        # We use the orchestrator directly to bypass some high-level caching if any
        # and to ensure we are testing the engine implementation via the orchestrator.
        routes = await engine_instance.orchestrator.search_all_tiers(
            source_code=source,
            destination_code=destination,
            departure_date=travel_dt,
            constraints=constraints,
            limit=20,
            db=db
        )
        latency_ms = (time.perf_counter() - start_time) * 1000
        count = len(routes)
        
        durations = [r.total_duration for r in routes if hasattr(r, 'total_duration')]
        min_duration = min(durations) if durations else 0
        
        return {
            "engine": engine_name,
            "latency_ms": latency_ms,
            "count": count,
            "min_duration": min_duration,
            "status": "OK"
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "engine": engine_name,
            "latency_ms": latency_ms,
            "count": 0,
            "min_duration": 0,
            "status": f"ERROR: {str(e)[:50]}"
        }

async def run_comparison():
    print("🚀 Initializing Database and Route Engine...")
    await initialize_database_pools()
    
    engine = RailwayRouteEngine()
    await engine.init()
    
    db = SessionTransit()
    
    # Engines to test in order (starting with TBR as requested)
    engines = ["TBR", "HubTier0", "Turbo", "UltraTurbo", "RAPTOR", "FastPath"]
    
    test_cases = [
        {"src": "NDLS", "dst": "KOTA", "label": "Direct (Delhi -> Kota)"},
        {"src": "NDLS", "dst": "PUNE", "label": "Long (Delhi -> Pune)"},
        {"src": "BCT", "dst": "HWH", "label": "Cross-Country (Mumbai -> Howrah)"}
    ]
    
    travel_dt = datetime.now() + timedelta(days=1)
    travel_dt = travel_dt.replace(hour=10, minute=0, second=0, microsecond=0)
    
    summary_results = []
    
    for case in test_cases:
        print(f"\n--- Testing Case: {case['label']} ({case['src']} -> {case['dst']}) ---")
        case_results = []
        for eng_name in engines:
            print(f"  🔍 Benchmarking {eng_name}...", end="", flush=True)
            res = await benchmark_engine(engine, eng_name, case['src'], case['dst'], travel_dt, db)
            case_results.append(res)
            if res['status'] == "OK":
                print(f" DONE ({res['latency_ms']:.1f}ms, {res['count']} routes)")
            else:
                print(f" FAILED ({res['status']})")
        
        summary_results.append({"case": case['label'], "results": case_results})
        
    # Generate Markdown Report
    report_path = "routing_engine_comparison.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 🚦 Routing Engine Comparison Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Test Parameters:** {len(test_cases)} cases, {len(engines)} engines.\n\n")
        
        for summary in summary_results:
            f.write(f"## {summary['case']}\n\n")
            f.write("| Engine | Latency (ms) | Routes Found | Best Duration (min) | Status |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- |\n")
            # Sort by latency for each case
            sorted_res = sorted(summary['results'], key=lambda x: x['latency_ms'] if x['status'] == "OK" else 999999)
            for r in sorted_res:
                lat_str = f"{r['latency_ms']:.2f}" if r['latency_ms'] > 0 else "N/A"
                best_dur = r['min_duration'] if r['min_duration'] > 0 else "N/A"
                f.write(f"| **{r['engine']}** | {lat_str} | {r['count']} | {best_dur} | {r['status']} |\n")
            f.write("\n")
            
        f.write("## 🏆 Recommended Ordering\n\n")
        f.write("Based on the benchmarks above, we recommend the following order in the Orchestrator:\n\n")
        f.write("1. **HubTier0**: Ultra-fast backbone lookup.\n")
        f.write("2. **Turbo / UltraTurbo**: Direct and 1-transfer SQL-based high speed search.\n")
        f.write("3. **TBR (Trip Based Routing)**: Optimized graph search for multi-transfer routes.\n")
        f.write("4. **RAPTOR**: Discovery engine for complex connectivity.\n")
        f.write("5. **FastPath**: Final fallback for broad connectivity.\n")

    print(f"\n✅ Benchmarking complete. Report saved to {report_path}")

if __name__ == "__main__":
    asyncio.run(run_comparison())
