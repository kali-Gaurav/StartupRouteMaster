import os
import sys
import asyncio
import logging
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Mock pandas if missing (requested by sklearn internals)
try:
    import pandas
except ImportError:
    from unittest.mock import MagicMock
    sys.modules["pandas"] = MagicMock()

async def test_graph_and_raptor():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("verify-raptor")
    
    logger.info("🔍 Verifying Task 11: Graph Optimization & mmap...")
    
    try:
        from core.route_engine.builder import GraphBuilder
        from core.route_engine.raptor import OptimizedRAPTOR
        from core.route_engine.constraints import RouteConstraints
        from database.session import initialize_database_pools
        from concurrent.futures import ThreadPoolExecutor
        
        # 1. Initialize Pools
        await initialize_database_pools()
        
        # 2. Build Graph (will trigger vectorization)
        executor = ThreadPoolExecutor(max_workers=1)
        builder = GraphBuilder(executor)
        
        test_date = datetime(2025, 3, 20) # Use a date that might have data
        logger.info(f"Building graph for {test_date}...")
        graph = await builder.build_graph(test_date)
        
        # 3. Verify mmap availability
        snapshot = graph.snapshot
        if snapshot._segments_data is not None:
            logger.info(f"✅ Vectorized Segments Mapped: {snapshot._segments_data.shape}")
        else:
            logger.error("❌ Vectorized Segments MISSING")

        if snapshot._transfers_data is not None:
            logger.info(f"✅ Vectorized Transfers Mapped: {snapshot._transfers_data.shape}")
        else:
            logger.error("❌ Vectorized Transfers MISSING")
            
        # 4. Test RAPTOR
        raptor = OptimizedRAPTOR(max_transfers=2)
        constraints = RouteConstraints()
        
        # Pick 2 station IDs from the cache
        stop_ids = list(snapshot.stop_cache.keys())
        if len(stop_ids) < 2:
            logger.warning("Not enough stops in DB to test routing. Skipping search test.")
            return

        source = stop_ids[0]
        dest = stop_ids[1]
        
        logger.info(f"Testing RAPTOR search from {source} to {dest}...")
        start_time = _time.time()
        routes = await raptor.find_routes(source, dest, test_date, constraints, graph=graph)
        end_time = _time.time()
        
        logger.info(f"✅ RAPTOR search completed in {(end_time - start_time)*1000:.2f}ms")
        logger.info(f"✨ Task 11 Verification Complete.")
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}", exc_info=True)
        sys.exit(1)

import time as _time
if __name__ == "__main__":
    asyncio.run(test_graph_and_raptor())
