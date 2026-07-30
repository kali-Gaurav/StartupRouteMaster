import asyncio
import sys
import os
import time
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.route_engine.data_provider import DataProvider
from services.multi_layer_cache import multi_layer_cache

async def verify_task_12():
    print("\n>>> STARTING VERIFICATION: MVP TASK 12 (BATCHED LOOKUPS)")
    
    await multi_layer_cache.initialize()
    provider = DataProvider()
    
    # Mock RapidAPI client to simulate successful responses
    provider.rapidapi_client = MagicMock()
    # Mock verify_seat_availability_unified since batch calls it
    async def mock_unified(*args, **kwargs):
        return {"status": "verified", "available_seats": 50, "source": "rapidapi"}
    
    provider.verify_seat_availability_unified = AsyncMock(side_effect=mock_unified)

    # 1. Prepare 12 queries (should trigger 3 batches: 5, 5, 2)
    queries = []
    for i in range(12):
        queries.append({
            "train_number": f"T{i}",
            "from_station": "NDLS",
            "to_station": "KOTA",
            "date": "2026-03-15",
            "quota": "GN",
            "journey_id": f"J{i}"
        })

    # 2. Test Batching Latency (Subtask 12.4)
    print(f"\n[12.4] Executing batch of {len(queries)} lookups...")
    start_time = time.perf_counter()
    results = await provider.verify_seat_availability_batch(queries)
    duration = (time.perf_counter() - start_time) * 1000
    
    print(f"  Total Duration: {duration:.2f}ms")
    print(f"  Results Count: {len(results)}")
    
    # We expect 2 sleeps of 200ms = 400ms minimum
    assert duration >= 400
    assert len(results) == 12
    print("  SUCCESS: Correct batching delay detected.")

    # 3. Test Cache Integration (Subtask 12.3)
    print("\n[12.3] Testing Cache hit bypass in batch...")
    # Inject one result into Redis
    if multi_layer_cache.redis:
        q_cached = queries[0]
        cache_key = f"verify_seat:{q_cached['train_number']}:{q_cached['from_station']}:{q_cached['to_station']}:{q_cached['date']}:{q_cached['quota']}:SL"
        await multi_layer_cache.redis.setex(cache_key, 60, '{"status": "verified", "available_seats": 99, "source": "cache"}')
        
        # Reset mock call count
        provider.verify_seat_availability_unified.reset_mock()
        
        # Re-run batch for 2 queries (1 cached, 1 new)
        small_batch = [queries[0], queries[1]]
        res_mixed = await provider.verify_seat_availability_batch(small_batch)
        
        print(f"  Mixed Results: {[r['source'] for r in res_mixed]}")
        assert res_mixed[0]["source"] == "cache"
        assert res_mixed[1]["source"] == "rapidapi"
        # Mock should only have been called ONCE for queries[1]
        assert provider.verify_seat_availability_unified.call_count == 1
        print("  SUCCESS: Batching correctly skips cached results.")

    print("\n✅ ALL MVP TASK 12 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_12())
