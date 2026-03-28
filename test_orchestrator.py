
import asyncio
import logging
from datetime import datetime
import sys
import os
from collections import Counter

# Ensure backend is in path
sys.path.insert(0, os.path.abspath("backend"))

from database.session import init_db
from core.route_engine.engine import route_engine
from core.route_engine.constraints import RouteConstraints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_orchestrator")

async def run_test(source_code, dest_code, test_name):
    print(f"{'='*20} {test_name}: {source_code} -> {dest_code} {'='*20}")
    
    # 1. Setup
    travel_date = datetime(2026, 4, 2)
    constraints = RouteConstraints(max_results=50, timeout_ms=30000)

    # 2. Run Orchestrated Search
    start_time = datetime.now()
    # The main search method now uses the orchestrator with intelligent expansion
    routes = await route_engine.search(source_code, dest_code, travel_date, constraints)
    end_time = datetime.now()
    
    print(f"Search took: {(end_time - start_time).total_seconds():.2f}s")
    print(f"Total Routes Found: {len(routes)}")
    
    if not routes:
        logger.error("TEST FAILED: No routes were found.")
        return

    # 3. Analyze Engine Contributions
    engine_counts = Counter(r.metadata.get('engine', 'unknown') for r in routes)
    print("Engine Contributions:")
    for engine, count in engine_counts.items():
        print(f"  - {engine}: {count} routes")

    # 4. Print Sample Routes
    print("Sample Routes:")
    for i, r in enumerate(routes[:5]): # Print first 5 routes
        transfer_str = f"{len(r.transfers)} transfers" if r.transfers else "direct"
        print(f"  Route {i+1} ({r.metadata.get('engine')}): {transfer_str}, Duration: {r.total_duration} mins")
    
    # 5. Verify different transfer counts are present
    transfer_counts = Counter(len(r.transfers) for r in routes)
    print(f"Yield by transfer count: {dict(transfer_counts)}")
    print(f"{'='*20} END TEST: {test_name} {'='*20}")
    return True


async def main():
    # 0. Initialize DB
    await init_db()

    # Test 1: High-yield search between major hubs
    await run_test("NDLS", "MMCT", "High-Yield Test")
    
    # Test 2: Low-yield search that should trigger expansion
    # GHY (Guwahati) to PUNE is a long, complex route likely to have low direct yield
    await run_test("GHY", "PUNE", "Low-Yield Expansion Test")

if __name__ == "__main__":
    asyncio.run(main())
