import asyncio
import time
import logging
import statistics
from core.nexus.financial.rollback import atomic_fiber
from database.session import SessionUser, init_db
from core.infrastructure.container import container
import os

# Set testing environment
os.environ["DATABASE_URL"] = "sqlite:///test_perf.db"
os.environ["ENVIRONMENT"] = "testing"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phase5.audit")

@atomic_fiber
async def mock_search_unlock():
    """Simulated fast operation to measure WAL overhead."""
    # This represents a successful transaction
    return {"status": "success"}

async def benchmark_saga_overhead(iterations=100):
    """
    [Task 45] Final Density Audit.
    Measures the overhead introduced by the Saga WAL (nexus_sagas.db) and @atomic_fiber.
    Target: < 50ms overhead.
    """
    logger.info(f"📊 Benchmarking Nexus Saga WAL Overhead ({iterations} iterations)...")
    
    await container.get("db")
    await init_db()
    
    latencies = []
    
    for _ in range(iterations):
        start_time = time.perf_counter()
        await mock_search_unlock()
        elapsed = (time.perf_counter() - start_time) * 1000 # to ms
        latencies.append(elapsed)
        
    avg_latency = statistics.mean(latencies)
    p95_latency = statistics.quantiles(latencies, n=20)[18] # P95
    max_latency = max(latencies)
    
    logger.info(f"   Avg Latency: {avg_latency:.2f} ms")
    logger.info(f"   P95 Latency: {p95_latency:.2f} ms")
    logger.info(f"   Max Latency: {max_latency:.2f} ms")
    
    if p95_latency < 50:
         logger.info("✅ Phase 5 Performance Target met (< 50ms).")
    else:
         logger.warning("⚠️ Phase 5 Performance Alert: Saga overhead exceeds 50ms target.")

if __name__ == "__main__":
    asyncio.run(benchmark_saga_overhead())
