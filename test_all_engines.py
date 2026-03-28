
import asyncio
import logging
from datetime import datetime
import sys
import os
from collections import Counter
from typing import List

# Ensure backend is in path
sys.path.insert(0, os.path.abspath("backend"))

from database.session import init_db
from core.route_engine.engine import route_engine
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Route, RouteSegment, TransferConnection

# Import all engines
from core.route_engine.ultra_turbo import UltraTurboDirectEngine
from core.route_engine.turbo_router import TurboRouter
from core.route_engine.fast_router import FastPathRouter
from core.route_engine.tbr_router import TripBasedRouter
from core.route_engine.raptor import OptimizedRAPTOR

logging.basicConfig(level=logging.INFO)
# Silence chatty loggers for this test
logging.getLogger("core.route_engine.engine").setLevel(logging.WARNING)
logging.getLogger("core.route_engine.builder").setLevel(logging.WARNING)
logging.getLogger("tbr_router").setLevel(logging.WARNING)
logging.getLogger("raptor").setLevel(logging.WARNING)

# 10 Diverse Station Pairs
STATION_PAIRS = [
    ("NDLS", "MMCT"),  # Major Hub <-> Major Hub (West)
    ("HWH", "MAS"),   # Major Hub <-> Major Hub (East-South)
    ("SBC", "PUNE"),   # IT Hub <-> IT Hub
    ("GHY", "ERS"),    # Cross-country, difficult (North-East to South)
    ("JAT", "CAPE"),   # Extreme North-South
    ("ADI", "PURI"),   # West-East
    ("JP", "BPL"),     # Regional <-> Regional (North-West to Central)
    ("LKO", "RMM"),    # North -> Extreme South (Religious route)
    ("VSKP", "GOA"),   # Coastal, likely requires transfers
    ("PNBE", "UBL")    # East -> South-West
]

async def test_engine(engine_name: str, engine_instance: object, pairs: List[tuple], graph, date):
    """Reusable test harness for a single engine."""
    print(f"{'='*25} TESTING ENGINE: {engine_name.upper()} {'='*25}")
    total_routes_found = 0
    total_time = 0.0

    for source_code, dest_code in pairs:
        print(f"  Testing {source_code} -> {dest_code}...", end='', flush=True)
        constraints = RouteConstraints(max_results=50, timeout_ms=10000)
        
        start_time = datetime.now()
        
        # Engines have different find_routes signatures, adapt the call
        routes: List[Route] = []
        try:
            from utils.station_utils import get_metro_group_codes
            src_codes = get_metro_group_codes(source_code)
            dst_codes = get_metro_group_codes(dest_code)
            
            src_ids = []
            for code in src_codes:
                s = graph.get_stop_by_code(code)
                if s: src_ids.append(s.id)
                
            dst_ids = []
            for code in dst_codes:
                d = graph.get_stop_by_code(code)
                if d: dst_ids.append(d.id)

            if not src_ids or not dst_ids:
                print(f" Skipping (invalid IDs: {source_code}->{dest_code})")
                continue

            if engine_name in ["TBR", "RAPTOR"]:
                routes = await engine_instance.find_routes(src_ids, dst_ids, date, constraints, graph)
            elif engine_name == "FastPath":
                # It's synchronous, so wrap in to_thread
                routes = await asyncio.to_thread(engine_instance.find_routes, src_ids, dst_ids, date, constraints)
            elif engine_name in ["UltraTurbo", "Turbo"]:
                # These take codes
                raw_routes = await engine_instance.find_routes(source_code, dest_code, date, limit=50)
                # Hydrate the raw dicts into Route objects for consistent analysis
                if raw_routes and isinstance(raw_routes[0], dict):
                    # Simplified hydration for test analysis
                    for r_dict in raw_routes:
                        rt = Route()
                        if r_dict.get("type") == "direct" and r_dict.get("train_no"):
                             rt.add_segment(RouteSegment(train_number=r_dict.get("train_no")))
                        elif r_dict.get("type") == "1-transfer" and r_dict.get("legs"):
                            rt.add_segment(RouteSegment(train_number=r_dict["legs"][0]["train"]))
                            rt.add_transfer(TransferConnection())
                            rt.add_segment(RouteSegment(train_number=r_dict["legs"][1]["train"]))
                        
                        if rt.segments: # Only append if segments were added
                            routes.append(rt)
                else:
                    routes = raw_routes # Should already be Route objects if API changed

            end_time = datetime.now()
            latency = (end_time - start_time).total_seconds()
            total_time += latency
            total_routes_found += len(routes)
            
            transfer_counts = Counter(len(r.transfers) for r in routes)
            yield_str = ", ".join([f"{k}T: {v}" for k, v in sorted(transfer_counts.items())])
            
            print(f" Done in {latency:.2f}s. Found: {len(routes):<3} ({yield_str if yield_str else '0 routes'})")

        except Exception as e:
            print(f" FAILED: {e}")

    print(f"  ----------------------------------------------------")
    print(f"  {engine_name} Summary: Found {total_routes_found} total routes in {total_time:.2f}s.")
    print(f"{'='*70}")


async def main():
    print("Initializing Database and Graph Snapshot...")
    await init_db()
    
    # Pre-load the graph once for all engines that need it
    graph_date = datetime(2026, 4, 2)
    graph = await route_engine._get_current_graph(graph_date)
    if not graph:
        print("FATAL: Could not load graph. Aborting test.")
        return
        
    print("Graph loaded. Starting engine stress test...")

    # Instantiate all engines
    engines = {
        "UltraTurbo": UltraTurboDirectEngine(),
        "Turbo": TurboRouter(),
        "FastPath": FastPathRouter(graph),
        "TBR": TripBasedRouter(max_transfers=3),
        "RAPTOR": OptimizedRAPTOR(max_transfers=3)
    }

    for name, instance in engines.items():
        await test_engine(name, instance, STATION_PAIRS, graph, graph_date)

if __name__ == "__main__":
    asyncio.run(main())
