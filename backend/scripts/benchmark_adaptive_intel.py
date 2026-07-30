import asyncio
import time
import logging
import random
from datetime import datetime, timedelta
import numpy as np
from typing import List, Dict

# Setup minimal logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("benchmark")

from services.search_service import SearchService
from core.route_engine.constraints import RouteConstraints
from core.data_utils.structures import Persona
from database.session import initialize_database_pools

async def run_benchmark():
    # Initialize DB pools first
    await initialize_database_pools()
    
    search_service = SearchService()
    
    # Common stations for benchmarking
    # These should be valid stop IDs in the DB
    # NDLS (7161), CSMT (1234), HWH (5678), MAS (9999)
    test_cases = [
        ("NDLS", "CSMT"), # Delhi -> Mumbai
        ("CSMT", "HWH"), # Mumbai -> Kolkata
        ("NDLS", "HWH"), # Delhi -> Kolkata
        ("HWH", "MAS"), # Kolkata -> Chennai
        ("NDLS", "MAS"), # Delhi -> Chennai
    ]
    
    personas = [Persona.FAST, Persona.ECONOMY, Persona.FAMILY, Persona.COMFORT]
    
    latencies = []
    
    logger.info("🚀 Starting Adaptive Intelligence Telemetry Audit...")
    logger.info("Mode: McRAPTOR + Neural Pruning + Stochastic Reliability")
    
    for i in range(3): # 3 trials for quick validation
        src, dst = random.choice(test_cases)
        persona = random.choice(personas)
        
        departure_dt = datetime.now() + timedelta(days=1)
        start_time = time.perf_counter()
        try:
            # We mock the graph if needed, but SearchService usually fetches it
            result = await search_service.search_routes(
                source=src,
                destination=dst,
                travel_date=departure_dt.strftime("%Y-%m-%d"),
                budget_category=persona.value,
                limit=10
            )
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
            
            logger.info(f"Trial {i+1:02d}: {src} -> {dst} | Persona: {persona.name:7s} | Latency: {latency_ms:6.1f}ms | Routes: {len(result.get('routes', []))}")
        except Exception as e:
            logger.error(f"Trial {i+1} failed: {e}")

    if not latencies:
        logger.error("No successful trials to audit.")
        return

    p50 = np.percentile(latencies, 50)
    p90 = np.percentile(latencies, 90)
    p99 = np.percentile(latencies, 99)
    avg = np.mean(latencies)
    
    logger.info("\n" + "="*40)
    logger.info("📊 TELEMETRY AUDIT RESULTS")
    logger.info("="*40)
    logger.info(f"Average Latency: {avg:6.2f} ms")
    logger.info(f"P50 Latency:     {p50:6.2f} ms")
    logger.info(f"P90 Latency:     {p90:6.2f} ms")
    logger.info(f"P99 Latency:     {p99:6.2f} ms")
    logger.info("="*40)
    
    if p99 < 150:
        logger.info("✅ STATUS: COMPLIANT (P99 < 150ms)")
    else:
        logger.warning("⚠️ STATUS: NON-COMPLIANT (P99 > 150ms)")
    
    logger.info("Audit Complete.")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
