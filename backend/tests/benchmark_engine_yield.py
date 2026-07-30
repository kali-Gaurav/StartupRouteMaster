import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# [Task 29] Engine Power-Yield & Transfer Benchmark
# Comparison of 0, 1, 2, 3 transfer discovery across all engines.

MAX_ENGINE_YIELD = 100
TARGET_PER_TRANSFER_GOAL = {0: 1, 1: 1, 2: 1, 3: 1}  # minimum coaches for each transfer category
SEARCH_DEPTH_STEPS = ["SHALLOW", "MEDIUM", "DEEP"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("routemaster.yield_benchmark")

# Define pairs for comprehensive testing
TEST_PAIRS = [
    ("GKP", "TVC", "Ultra Long-Distance (Multi-Transfer Challenge)"),
    ("NDLS", "MMCT", "Medium-Long Direct Backbone"),
]

async def benchmark_discovery():
    from core.route_engine.engine import RailwayRouteEngine
    from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
    from core.route_engine.base import RoutingRequest
    from core.route_engine.constraints import RouteConstraints
    from database.session import SessionTransit, initialize_database_pools, get_raw_transit_conn

    logger.info("🔥 [BENCHMARK] Initializing System for Yield Discovery...")
    # Initialize DB pools (Async)
    await initialize_database_pools()
    
    engine_base = RailwayRouteEngine()
    orch = UnifiedRoutingOrchestrator(engine_base)
    
    # Pre-Hydrate Graph
    target_date = datetime(2026, 4, 1)
    await engine_base._get_current_graph(target_date)
    
    db = SessionTransit()
    
    for src, dst, desc in TEST_PAIRS:
        logger.info(f"📍 Testing Pair: {src} -> {dst} ({desc})")
        
        from utils.station_utils import resolve_stations
        source_stop, dest_stop = await asyncio.to_thread(resolve_stations, db, src, dst)
        if not source_stop or not dest_stop:
            logger.error(f"❌ Failed to resolve stations {src} or {dst}")
            continue
            
        async with get_raw_transit_conn() as conn:
            src_cluster_ids = await orch.ultra_turbo._resolve_cluster_ids(conn, source_stop.code)
            dst_cluster_ids = await orch.ultra_turbo._resolve_cluster_ids(conn, dest_stop.code)

        req = RoutingRequest(
            source_code=src,
            destination_code=dst,
            departure_date=target_date,
            constraints=RouteConstraints(discovery_only=True), 
            limit=50,
            src_cluster_ids=src_cluster_ids,
            dst_cluster_ids=dst_cluster_ids,
            db_session=db
        )

        from core.nexus.audit.governor import nexus_governor
        gov_stats = await nexus_governor.get_stats()

        summary_rows = []
        
        # All available engines in orchestrator
        engines_to_test = list(orch.engines.keys())
        
        def _count_transfers(routes):
            transfers = {0: 0, 1: 0, 2: 0, 3: 0, "4+": 0}
            for r in routes:
                t_count = len(r.transfers)
                if t_count >= 4:
                    transfers["4+"] += 1
                elif t_count in transfers:
                    transfers[t_count] += 1
            return transfers

        def _goal_met(transfers):
            return all(transfers.get(k, 0) >= v for k, v in TARGET_PER_TRANSFER_GOAL.items())

        for name in engines_to_test:
            engine = orch.engines[name]
            logger.info(f"   🚀 Dispatching Engine: {name.upper()}...")

            best_engine_result = None
            for depth in SEARCH_DEPTH_STEPS:
                req.constraints.search_depth = depth
                req.constraints.max_results = MAX_ENGINE_YIELD
                st = time.perf_counter()

                try:
                    routes = await orch._discover_from_engine_async(name, engine, req, st, gov_stats)
                    latency_ms = (time.perf_counter() - st) * 1000

                    if len(routes) > MAX_ENGINE_YIELD:
                        routes = routes[:MAX_ENGINE_YIELD]

                    transfers = _count_transfers(routes)
                    yield_total = len(routes)

                    summary = {
                        "engine": name,
                        "depth": depth,
                        "latency": latency_ms,
                        "total": yield_total,
                        "0-tr": transfers[0],
                        "1-tr": transfers[1],
                        "2-tr": transfers[2],
                        "3-tr": transfers[3],
                        "4+tr": transfers["4+"],
                        "goal_met": _goal_met(transfers)
                    }

                    logger.info(f"      depth={depth} | total={yield_total} | 0={transfers[0]},1={transfers[1]},2={transfers[2]},3={transfers[3]},4+={transfers['4+']} | goal_met={summary['goal_met']}")

                    if not best_engine_result or yield_total > best_engine_result['total']:
                        best_engine_result = summary

                    if summary['goal_met']:
                        break

                except Exception as e:
                    logger.error(f"      Engine {name} failed at depth {depth}: {e}")
                    continue

            # use best available depth result regardless of full goal
            if best_engine_result:
                summary_rows.append(best_engine_result)
            else:
                summary_rows.append({
                    "engine": name,
                    "depth": "N/A",
                    "latency": 0,
                    "total": 0,
                    "0-tr": 0,
                    "1-tr": 0,
                    "2-tr": 0,
                    "3-tr": 0,
                    "4+tr": 0,
                    "goal_met": False
                })

        # --- ASCII TABLE REPORT ---
        print("\n" + "="*95)
        print(f"📊 YIELD & PERFORMANCE BENCHMARK: {src} -> {dst}")
        print("="*95)
        header = f"{'ENGINE':<18} | {'DEPTH':<6} | {'LATENCY':<9} | {'YIELD':<6} | {'0-TR':<4} | {'1-TR':<4} | {'2-TR':<4} | {'3-TR':<4} | {'4+TR':<4} | {'GOAL':<4}"
        print(header)
        print("-" * 110)
        
        for row in summary_rows:
            print(f"{row['engine']:<18} | {row['depth']:<6} | {row['latency']:>7.2f}ms | {row['total']:>5} | {row['0-tr']:>4} | {row['1-tr']:>4} | {row['2-tr']:>4} | {row['3-tr']:>4} | {row['4+tr']:>4} | {str(row.get('goal_met', False)):<4}")
        print("="*110 + "\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(benchmark_discovery())
