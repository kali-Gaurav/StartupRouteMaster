import asyncio
import time
import logging
import sys
import os
from datetime import datetime
import random
from typing import List, Dict

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import RoutingRequest
from core.route_engine.constraints import RouteConstraints, DiscoveryModel
from core.route_engine import get_route_engine
from database.session import SessionLocal, initialize_database_pools, init_db
from services.agents.engineering_agents import ChronosAgent, AegisAgent
from services.agents.orchestrator import swarm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("audit.stress")

async def simulate_user_request(orchestrator: UnifiedRoutingOrchestrator, req_id: int):
    """Simulates a high-pressure search request."""
    sources = ["NDLS", "BCT", "MAS", "HWH", "SBC"]
    destinations = ["DLI", "ADI", "CNB", "LKO", "JP"]
    
    src = random.choice(sources)
    dst = random.choice(destinations)
    
    # [Task 117.1] Create real RoutingRequest context
    request = RoutingRequest(
        source_code=src,
        destination_code=dst,
        departure_date=datetime(2024, 12, 25),
        constraints=RouteConstraints(discovery_model=DiscoveryModel.OMNISCIENT),
        limit=5,
        force_refresh=True # Force compute to stress agents
    )
    
    # Attach a session for the orchestrator to use
    with SessionLocal() as db:
        request.db_session = db
        start = time.monotonic()
        try:
            result = await orchestrator.stream_all_tiers(request)
            duration = (time.monotonic() - start) * 1000
            return {"id": req_id, "duration": duration, "success": True}
        except Exception as e:
            return {"id": req_id, "error": str(e), "success": False}

async def run_industrial_audit(total_requests: int = 1000, concurrency: int = 50):
    """
    Executes a high-concurrency audit of the RouteMaster Swarm.
    Benchmarks latency, agent response times, and system resilience.
    """
    logger.info(f"\n🏗️ STARTING INDUSTRIAL PERFORMANCE AUDIT: {total_requests} Requests @ {concurrency} Concurrent\n")
    
    # [Task 117.2] Initialize DB Pools for concurrent sessions
    await initialize_database_pools()
    await init_db() # Ensure tables exist
    
    engine = get_route_engine()
    orchestrator = UnifiedRoutingOrchestrator(engine)
    chronos = ChronosAgent()
    aegis = AegisAgent()
    
    results = []
    start_time = time.monotonic()
    
    # Process in batches to control concurrency
    for i in range(0, total_requests, concurrency):
        batch_tasks = [simulate_user_request(orchestrator, i + j) for j in range(concurrency) if i + j < total_requests]
        batch_results = await asyncio.gather(*batch_tasks)
        results.extend(batch_results)
        
        # Periodic Vitals Check via Expert Agents
        if i % (concurrency * 5) == 0:
            vitals = await chronos.execute()
            chaos = await aegis.execute()
            logger.info(f"📊 Progress: {i}/{total_requests} | {vitals['summary']} | {chaos['summary']}")

    total_duration = time.monotonic() - start_time
    success_count = sum(1 for r in results if r["success"])
    latencies = [r["duration"] for r in results if r["success"]]
    
    p50 = sorted(latencies)[len(latencies)//2] if latencies else 0
    p95 = sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0
    
    logger.info("\n" + "="*50)
    logger.info(f"📈 AUDIT COMPLETE: {total_requests} requests in {total_duration:.2f}s")
    logger.info(f"✅ Success Rate: {(success_count/total_requests)*100:.2f}%")
    logger.info(f"⏱️ P50 Latency: {p50:.2f}ms")
    logger.info(f"⏱️ P95 Latency: {p95:.2f}ms")
    logger.info(f"🚀 Throughput: {total_requests/total_duration:.2f} req/s")
    logger.info("="*50 + "\n")

    if success_count / total_requests < 0.98:
        logger.error("❌ AUDIT FAILED: Reliability below industrial threshold (98%)")
        sys.exit(1)
    else:
        logger.info("🎉 AUDIT PASSED: Swarm is stable for Phase 6 Deployment.")

if __name__ == "__main__":
    # For local test, we use 500 requests to avoid hitting RapidAPI limits if applicable,
    # but the logic scales to 10k.
    asyncio.run(run_industrial_audit(total_requests=100, concurrency=4))
