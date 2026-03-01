import asyncio
import time
import httpx
import os
import sys

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app

async def measure(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> float:
    start = time.perf_counter()
    try:
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
    except Exception as e:
        print(f"Error on {url}: {e}")
        return 0
    return (time.perf_counter() - start) * 1000

async def stress_test(name: str, method: str, path: str, concurrency: int = 50, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Warmup
        await client.request(method, path, **kwargs)
        
        print(f"Starting {name} ({concurrency} concurrent requests)...")
        tasks = [measure(client, method, path, **kwargs) for _ in range(concurrency)]
        start_total = time.perf_counter()
        latencies = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_total
        
        valid_latencies = [l for l in latencies if l > 0]
        if not valid_latencies:
            print(f"❌ {name} failed all requests.")
            return

        avg_latency = sum(valid_latencies) / len(valid_latencies)
        print(f"✅ {name} Results: Avg {avg_latency:.2f} ms | Total {total_time:.2f}s")
        print("-" * 40)

async def stress_test_chat(name: str, concurrency: int = 50):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        print(f"Starting {name} ({concurrency} concurrent requests)...")
        tasks = [measure(client, "POST", "/api/chat", json={"message": "book ticket from delhi to mumbai", "session_id": f"perf_{i}"}) for i in range(concurrency)]
        start_total = time.perf_counter()
        latencies = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_total
        
        valid_latencies = [l for l in latencies if l > 0]
        if not valid_latencies:
            print(f"❌ {name} failed all requests.")
            return

        avg_latency = sum(valid_latencies) / len(valid_latencies)
        print(f"✅ {name} Results: Avg {avg_latency:.2f} ms | Total {total_time:.2f}s")
        print("-" * 40)

async def main():
    print("=" * 50)
    print("🚀 ROUTEMASTER FINAL PERFORMANCE BENCHMARK")
    print("=" * 50)
    
    # 1. Warm up Station Engine
    from services.station_search_service import station_search_engine
    station_search_engine._ensure_initialized()
    
    # 2. Warm up Cache
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.inmemory import InMemoryBackend
    FastAPICache.init(InMemoryBackend(), prefix="test-cache")
    
    # 1. Autocomplete
    await stress_test(
        "Station Autocomplete", 
        "GET", 
        "/api/stations/suggest?q=del",
        concurrency=100
    )
    
    # 2. Chat Intent
    await stress_test_chat("Chat Intent Engine", concurrency=50)
    
    # 3. Live Train Status
    await stress_test(
        "Live Train Status", 
        "GET", 
        "/api/realtime/train/12002/status",
        concurrency=30
    )
    
    # 4. Unified Search (Cached)
    await stress_test(
        "Unified Search - Cached", 
        "POST", 
        "/api/v2/search/unified",
        json={"source": "NDLS", "destination": "BCT", "date": "2026-05-15"},
        concurrency=50
    )

if __name__ == "__main__":
    asyncio.run(main())
