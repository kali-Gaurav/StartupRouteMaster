import asyncio
import logging
import time
from datetime import datetime
from core.route_engine.engine import RailwayRouteEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("engine_diag")

async def run_engine_diagnostic():
    print("\n--- RAILWAY ROUTE ENGINE DEEP DIAGNOSTIC ---")
    engine = RailwayRouteEngine()
    
    print("\n1. Initializing Engine...")
    start = time.perf_counter()
    await engine.init()
    duration = time.perf_counter() - start
    print(f"Engine Hot Boot took: {duration:.2f}s")
    
    if engine.graph:
        print(f"[OK] Graph loaded into memory.")
        print(f"Graph Date: {engine.graph.snapshot.date if engine.graph.snapshot else 'N/A'}")
        
        # Check Node Count
        nodes = len(engine.graph.nodes) if hasattr(engine.graph, 'nodes') else "Unknown"
        print(f"Total Nodes (Stations): {nodes}")
        
        # Check Reachability Bitset (Nexus Grade)
        has_bitset = hasattr(engine.graph.snapshot, '_trip_reachability_bitset')
        print(f"Reachability Index (Bitset): {'PRESENT' if has_bitset else 'MISSING'}")
        
        # Check Hot Stations
        hot_stations = ["NDLS", "BCT", "HWH", "CSMT", "MAS"]
        print("\n2. Verifying Hot Station Connectivity:")
        for code in hot_stations:
            # Check if station exists in graph
            if code in engine.graph.stops_by_code:
                print(f"  - {code}: FOUND")
            else:
                print(f"  - {code}: NOT IN GRAPH (Check data source)")
    else:
        print("[FAIL] Engine graph is NULL. Cannot perform diagnostics.")

    print("\n--- ENGINE DIAGNOSTIC COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(run_engine_diagnostic())
