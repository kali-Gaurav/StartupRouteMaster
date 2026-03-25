import asyncio
import time
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any

# Ensure we can import from backend
sys.path.append(os.path.abspath(os.path.join(os.getcwd())))
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "backend")))

try:
    from backend.core.route_engine.orchestrator import UnifiedRoutingOrchestrator
    from backend.core.route_engine.engine import RailwayRouteEngine
    from backend.core.route_engine.constraints import RouteConstraints
    from backend.database.session import init_db
    from backend.database.config import Config
except ImportError:
    try:
        from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
        from core.route_engine.engine import RailwayRouteEngine
        from core.route_engine.constraints import RouteConstraints
        from database.session import init_db
        from database.config import Config
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("stress-test")

async def run_stress_test(num_requests: int = 50):
    logger.info("🧪 INITIALIZING STRESS TEST SUITE...")
    
    # 1. Database & Engine Setup
    try:
        await init_db()
        # RailwayRouteEngine is a singleton
        engine = RailwayRouteEngine()
        # Manually trigger graph loading if needed
        # We'll assume the orchestrator handles it or calls engine methods
        
        # UnifiedRoutingOrchestrator is usually instantiated with the engine
        orchestrator = UnifiedRoutingOrchestrator(engine)
        logger.info("✅ Engine & Orchestrator ready.")
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}", exc_info=True)
        return

    # 2. Test Configuration
    test_cases = [
        ("NDLS", "BCT"), # Delhi to Mumbai
        ("HWH", "MAS"),  # Howrah (Kolkata) to Chennai
        ("SBC", "NZM"),  # Bangalore to Delhi
        ("MAS", "NDLS"), # Chennai to Delhi
        ("BCT", "HWH")   # Mumbai to Howrah
    ]
    
    departure_date = datetime.now() + timedelta(days=5)
    
    # 3. Request Logic
    async def single_request(req_id: int, src: str, dst: str) -> Dict[str, Any]:
        constraints = RouteConstraints()
        # Note: RouteConstraints doesn't take params in constructor usually, 
        # but let's check or just set fields
        constraints.departure_date = departure_date
        constraints.preferred_class = "SL"
        constraints.discovery_only = True
        
        start = time.perf_counter()
        try:
            total_routes = 0
            batches_count = 0
            # stream_all_tiers yields batches of List[Route]
            async for batch in orchestrator.stream_all_tiers(
                src, dst, departure_date, constraints, skip_heavy=True
            ):
                total_routes += len(batch)
                batches_count += 1
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            
            return {
                "id": req_id,
                "src": src,
                "dst": dst,
                "latency_ms": latency_ms,
                "total_routes": total_routes,
                "batches": batches_count,
                "error": None
            }
        except Exception as e:
            logger.error(f"Request {req_id} ({src}->{dst}) failed: {e}")
            return {
                "id": req_id,
                "src": src,
                "dst": dst,
                "latency_ms": 0,
                "total_routes": 0,
                "batches": 0,
                "error": str(e)
            }

    # 4. Phase 1: Sequential Warmup
    logger.info("🔥 Phase 1: Sequential Warmup (5 requests)...")
    for i in range(5):
        src, dst = test_cases[i % len(test_cases)]
        res = await single_request(i, src, dst)
        if res["error"]:
            logger.warning(f"Warmup Request {i} failed: {res['error']}")
        else:
            logger.info(f"Warmup {i}: {res['latency_ms']:.2f}ms - {res['total_routes']} routes")

    # 5. Phase 2: Concurrent Burst
    logger.info(f"💥 Phase 2: Concurrent Burst ({num_requests} requests)...")
    tasks = []
    for i in range(num_requests):
        src, dst = test_cases[i % len(test_cases)]
        tasks.append(single_request(i + 5, src, dst))
    
    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_time
    
    # 6. Analysis
    successes = [r for r in results if r["error"] is None]
    errors = [r for r in results if r["error"] is not None]
    latencies = [r["latency_ms"] for r in successes]
    
    logger.info("=" * 40)
    logger.info(f"📈 STRESS TEST RESULTS ({num_requests} Concurrent Requests)")
    logger.info("=" * 40)
    logger.info(f"Total Time:    {total_time:.2f}s")
    logger.info(f"Throughput:    {num_requests / total_time:.2f} req/s")
    logger.info(f"Successes:     {len(successes)}")
    logger.info(f"Failures:      {len(errors)}")
    
    if latencies:
        logger.info(f"Avg Latency:   {sum(latencies) / len(latencies):.2f}ms")
        logger.info(f"Min Latency:   {min(latencies):.2f}ms")
        logger.info(f"Max Latency:   {max(latencies):.2f}ms")
        sorted_lats = sorted(latencies)
        p95 = sorted_lats[int(len(sorted_lats) * 0.95)]
        p99 = sorted_lats[int(len(sorted_lats) * 0.99)] if len(sorted_lats) >= 100 else p95
        logger.info(f"P95 Latency:   {p95:.2f}ms")
        logger.info(f"P99 Latency:   {p99:.2f}ms")
    
    logger.info("=" * 40)
    
    if errors:
        logger.error("🛑 Top 5 Error Samples:")
        for e in errors[:5]:
            logger.error(f"- {e['src']}->{e['dst']}: {e['error']}")

if __name__ == "__main__":
    # Allow passing num_requests from CLI
    n = 50
    if len(sys.argv) > 1:
        try: n = int(sys.argv[1])
        except: pass
    
    asyncio.run(run_stress_test(n))
