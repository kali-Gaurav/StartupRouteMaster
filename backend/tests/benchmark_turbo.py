import sys
import os
import time
import asyncio
import logging
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.turbo_router import TurboRouter
from database.session import SessionTransit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("turbo-bench")

async def benchmark_turbo():
    from core.infrastructure.container import container
    from database.session import SessionTransit
    
    # Initialize DB via IoC
    await container.get("db")
    
    router = TurboRouter()
    
    # Test pairs (Popular Routes)
    test_cases = [
        ("NDLS", "HWH"), # Delhi to Howrah
        ("BZA", "SDAH"), # Vijayawada to Sealdah
        ("MS", "PUNE"),  # Chennai to Pune
        ("PNBE", "NDLS") # Patna to Delhi
    ]
    
    date = datetime(2026, 3, 20, 10, 0, 0)
    
    logger.info(f"🚀 Starting TurboRouter Benchmark (Top 50 Dynamic Hubs)...")
    
    for src, dst in test_cases:
        start = time.perf_counter()
        # Run in thread since find_routes is sync
        routes = await asyncio.to_thread(router.find_routes, src, dst, date, 15)
        end = time.perf_counter()
        
        latency_ms = (end - start) * 1000
        logger.info(f"Query {src} -> {dst}: {len(routes)} routes found in {latency_ms:.2f}ms")
        
        if latency_ms > 50:
            logger.warning(f"⚠️ Latency exceeded 50ms for {src}->{dst}")
        elif latency_ms < 10:
            logger.info(f"⚡ Elite performance detected (<10ms)")

if __name__ == "__main__":
    asyncio.run(benchmark_turbo())
