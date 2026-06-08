import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set

import sys
import os
# Ensure backend package root is importable
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.constraints import RouteConstraints
from core.route_engine.graph import TimeDependentGraph
from database.session import initialize_database_pools, SessionTransit
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("raptor.hardening_benchmark")

async def run_benchmark():
    logger.info("🔥 [BENCHMARK] Starting RAPTOR Hardening Verification (Tasks 15 & 16)...")
    
    # 1. Initialize DB and Graph
    await initialize_database_pools()
    db = SessionTransit()
    
    # We need a graph instance. 
    # For a real benchmark, we'd load a full graph, but here we'll try to get the existing one if possible.
    from core.route_engine.engine import RailwayRouteEngine
    engine_base = RailwayRouteEngine()
    target_date = datetime(2026, 5, 20)
    graph = await engine_base._get_current_graph(target_date)
    
    if not graph:
        logger.error("❌ Failed to load graph snapshot. Ensure railway_data.db is populated.")
        return

    raptor = OptimizedRAPTOR(max_transfers=3)
    
    # 2. Define Test Scenarios
    # Scenario 1: High-fan-out Round 0 (Many source stations, e.g. from a cluster)
    # Scenario 2: Early Exit potential (Short route vs long search window)
    
    test_cases = [
        {
            "name": "Multi-Source Cluster Search (Round 0 stress)",
            "src_codes": ["NDLS", "NZM", "DLI"], # Delhi cluster
            "dst_codes": ["MMCT"],
            "window": 1440, # 24h
        },
        {
            "name": "Early Exit Optimization (Direct Route Available)",
            "src_codes": ["GKP"],
            "dst_codes": ["LKO"], # Close destination
            "window": 1440,
        }
    ]

    for tc in test_cases:
        logger.info(f"\n🏃 Running Test: {tc['name']}")
        
        # Resolve IDs
        from utils.station_utils import resolve_stations
        source_ids = []
        for code in tc['src_codes']:
            s = db.execute(text("SELECT id FROM stops WHERE code = :code"), {"code": code}).fetchone()
            if s: source_ids.append(s[0])
            
        dest_ids = set()
        for code in tc['dst_codes']:
            s = db.execute(text("SELECT id FROM stops WHERE code = :code"), {"code": code}).fetchone()
            if s: dest_ids.add(s[0])
        
        dest_ids = list(dest_ids)

        if not source_ids or not dest_ids:
            logger.warning(f"⚠️ Skipping {tc['name']} - stations not found.")
            continue

        constraints = RouteConstraints(range_minutes=tc['window'])
        
        # Benchmark Round 0 Parallel vs Sequential (Manual toggle)
        # We'll just run it with the current implementation and check telemetry logs (if we add print to telemetry)
        
        st = time.perf_counter()
        # Note: find_routes is async but calls _search_multi_departure_sync via thread
        routes = await raptor.find_routes(source_ids, dest_ids, target_date, constraints, graph)
        et = time.perf_counter()
        
        logger.info(f"✅ Completed in {(et-st)*1000:.2f}ms. Found {len(routes)} routes.")
        
        # Inspect RAPTOR state if needed (metrics are global)
        from utils.metrics import RAPTOR_EARLY_EXIT_TOTAL, RAPTOR_PRUNED_BRANCHES_TOTAL
        # In a real prometheus setup we'd query the registry. 
        # Here we can just check if they were incremented if we had access to the registry object.
        
    logger.info("\n✨ [BENCHMARK] Hardening verification complete.")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
