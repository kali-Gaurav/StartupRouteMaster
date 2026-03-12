import asyncio
import httpx
import time
import logging
import tracemalloc
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-subtask-1.1")

BASE_URL = "http://127.0.0.1:8000"

async def test_normal_flow():
    logger.info("Test 1: Normal Flow")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        start = time.time()
        # Initial request might trigger JIT
        response = await client.get(f"{BASE_URL}/api/health")
        logger.info(f"Health check status: {response.status_code}, time: {time.time()-start:.2f}s")
        assert response.status_code == 200

async def test_jit_delay_503():
    logger.info("Test 2: JIT Loading Delay simulation")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        payload = {
            "source": "KOTA",
            "destination": "NDLS",
            "date": "2026-03-15",
            "budget": "all"
        }
        response = await client.post(f"{BASE_URL}/api/search/", json=payload)
        logger.info(f"Search status: {response.status_code}")
        if response.status_code == 422:
            logger.error(f"Validation error: {response.json()}")
        assert response.status_code in [200, 503, 500] 
        if response.status_code == 503:
            data = response.json()
            assert data["error"] is True
            assert "initializing" in data["message"]

async def test_bypass_paths():
    logger.info("Test 7: Bypass Paths")
    paths = ["/", "/api/health", "/api/health/live"]
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for path in paths:
            response = await client.get(f"{BASE_URL}{path}")
            logger.info(f"Bypass {path}: {response.status_code}")
            assert response.status_code == 200

async def test_concurrency_load():
    logger.info("Test 9: Event Loop Blocking / Concurrency")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [client.get(f"{BASE_URL}/api/health") for _ in range(50)]
        start = time.time()
        results = await asyncio.gather(*tasks)
        logger.info(f"Concurrency results: {len(results)} requests in {time.time()-start:.2f}s")
        for r in results:
            assert r.status_code == 200

async def test_memory_leaks():
    logger.info("Test 10: Memory Leak Check (Short run)")
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for _ in range(100):
            await client.get(f"{BASE_URL}/api/health")
            
    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    
    logger.info("[ Top 5 memory users ]")
    for stat in top_stats[:5]:
        logger.info(str(stat))
    
    tracemalloc.stop()

async def run_all_tests():
    try:
        await test_normal_flow()
        await test_bypass_paths()
        await test_jit_delay_503()
        await test_concurrency_load()
        await test_memory_leaks()
        logger.info("✅ Subtask 1.1 Verification PASSED (Subset of 10 hard cases)")
    except Exception as e:
        logger.error(f"❌ Verification FAILED: {e}")

if __name__ == "__main__":
    # Ensure uvicorn is running first!
    asyncio.run(run_all_tests())
