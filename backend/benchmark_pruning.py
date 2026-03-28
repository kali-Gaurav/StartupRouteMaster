
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List

# Add backend directory to path
import sys
import os
backend_path = os.path.abspath(os.path.dirname(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import asyncio
import logging
import time
from datetime import datetime, timedelta

# Add backend directory to path
import sys
import os
backend_path = os.path.abspath(os.path.dirname(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from database.session import initialize_database_pools
from core.route_engine.constraints import RouteConstraints
from core.route_engine.raptor import OptimizedRAPTOR
from core.route_engine.graph import StaticGraphSnapshot

async def benchmark_pruning():
    print("🚀 [INIT] Loading Graph Snapshot & Initializing Pools...")
    await initialize_database_pools()
    
    # Load the latest snapshot directly (V10.0 optimized)
    snapshot_path = os.path.join(backend_path, "snapshots", "graph_snapshot_20260330.pkl")
    if not os.path.exists(snapshot_path):
        print(f"⚠️ Snapshot not found at {snapshot_path}, falling back to dynamic build...")
        from core.route_engine.builder import GraphBuilder
        builder = GraphBuilder()
        graph = await builder.build_optimized_graph(datetime.now())
    else:
        import pickle
        with open(snapshot_path, "rb") as f:
            snapshot = pickle.load(f)
        from core.route_engine.graph import TimeDependentGraph
        graph = TimeDependentGraph(snapshot=snapshot)
        # Hydrate stop_cache for stop_by_code
        graph.stop_cache = snapshot.stop_cache
    
    engine = OptimizedRAPTOR(max_transfers=2)
    
    # MAS (Chennai) to SBC (Bangalore) - MAS: 121, SBC: 153 (Typical IDs)
    # Using codes to resolve via graph
    s_stop = graph.get_stop_by_code("MAS")
    d_stop = graph.get_stop_by_code("SBC")
    
    if not s_stop or not d_stop:
        print("❌ Error: MAS or SBC not found in graph.")
        return

    travel_date = datetime.now() + timedelta(days=2)
    constraints = RouteConstraints(
        max_transfers=2,
        range_minutes=1440, 
        timeout_ms=10000
    )

    print(f"\n⚡ [BENCHMARK] Searching {s_stop.name} -> {d_stop.name} (Pruning Active)...")
    
    # Warm up
    await engine.find_routes(s_stop.id, d_stop.id, travel_date, constraints, graph)
    
    start = time.perf_counter()
    results = await engine.find_routes(s_stop.id, d_stop.id, travel_date, constraints, graph)
    end = time.perf_counter()
    
    duration = (end - start) * 1000
    print(f"\n✅ Benchmarking Complete:")
    print(f"  ├─ Latency: {duration:.2f}ms")
    print(f"  ├─ Results: {len(results)} optimal routes found")
    print(f"  └─ Status : {'FIBER_SPEED' if duration < 100 else 'NORMAL'}")

if __name__ == "__main__":
    asyncio.run(benchmark_pruning())

if __name__ == "__main__":
    asyncio.run(benchmark_pruning())
