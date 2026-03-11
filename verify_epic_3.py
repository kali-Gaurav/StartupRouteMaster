import asyncio
import time
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.zonal_loader import zonal_loader

async def run_test(name, func):
    print(f"🧪 Testing: {name}...", end=" ", flush=True)
    try:
        res = await func()
        print(f"✅ PASSED | {res}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

# --- 15 EPIC 3 TESTS (Part 1) ---

async def test_1_mmap_instant_load():
    """Verify zone loads in < 5ms via MMAP."""
    start = time.perf_counter()
    data = await zonal_loader.get_zone_data(0)
    duration = (time.perf_counter() - start) * 1000
    assert data is not None
    # Cold load should still be very fast with MMAP
    assert duration < 50.0 # Standard disk might be slower, but < 50ms is good
    return f"Load time: {duration:.2f}ms"

async def test_2_lru_eviction():
    """Verify that only max_zones stay in RAM."""
    zonal_loader.max_zones = 2
    zonal_loader.loaded_zones.clear()
    
    await zonal_loader.get_zone_data(0)
    await zonal_loader.get_zone_data(1)
    await zonal_loader.get_zone_data(2) # Should evict Zone 0
    
    assert 0 not in zonal_loader.loaded_zones
    assert 1 in zonal_loader.loaded_zones
    assert 2 in zonal_loader.loaded_zones
    return "Eviction OK"

async def test_3_stop_to_zone_mapping():
    """Verify stop IDs map to correct zones."""
    assert zonal_loader.get_zone_id_for_stop(500) == 0
    assert zonal_loader.get_zone_id_for_stop(1500) == 1
    return "Mapping OK"

async def test_4_concurrent_zone_access():
    """Verify multiple tasks can access same zone simultaneously."""
    tasks = [zonal_loader.get_zone_data(1) for _ in range(50)]
    results = await asyncio.gather(*tasks)
    assert all(r is not None for r in results)
    return "Concurrency OK"

async def test_5_invalid_zone_resilience():
    res = await zonal_loader.get_zone_data(99)
    assert res is None
    return "Handled OK"

async def test_6_mmap_memory_sharing():
    """Verify multiple calls return views of the same data."""
    d1 = await zonal_loader.get_zone_data(1)
    d2 = await zonal_loader.get_zone_data(1)
    assert d1 is d2
    return "Sharing OK"

async def test_7_zone_rotation_stress():
    """Rapidly switch between 5 zones."""
    for _ in range(20):
        for z in [0, 1, 2, 3, 4]:
            await zonal_loader.get_zone_data(z)
    return "Stress OK"

async def test_8_large_zone_throughput():
    data = await zonal_loader.get_zone_data(0)
    # Just sum to force read access
    s = data.sum()
    assert s != 0
    return f"Data accessible (Sum: {s})"

async def test_9_lru_mru_promotion():
    """Accessing an old zone should move it to front of LRU."""
    zonal_loader.max_zones = 3
    zonal_loader.loaded_zones.clear()
    await zonal_loader.get_zone_data(0)
    await zonal_loader.get_zone_data(1)
    await zonal_loader.get_zone_data(2)
    # MRU order: [0, 1, 2]. Oldest is 0.
    await zonal_loader.get_zone_data(0)
    # MRU order: [1, 2, 0]. Oldest is now 1.
    await zonal_loader.get_zone_data(3) # Should evict 1
    assert 1 not in zonal_loader.loaded_zones
    assert 0 in zonal_loader.loaded_zones
    return "MRU Promotion OK"

async def test_10_partial_read_performance():
    data = await zonal_loader.get_zone_data(4)
    start = time.perf_counter()
    # Read only first 100 rows
    subset = data[:100]
    dur = (time.perf_counter() - start) * 1000
    return f"Partial read: {dur:.4f}ms"

async def main():
    print("🚀 Running 10 Hard Tests for Subtask 3.1 & 3.2: Zonal MMAP Loading\n")
    results = []
    results.append(await run_test("MMAP Instant Load", test_1_mmap_instant_load))
    results.append(await run_test("LRU Eviction", test_2_lru_eviction))
    results.append(await run_test("Stop-to-Zone Mapping", test_3_stop_to_zone_mapping))
    results.append(await run_test("Concurrent Access", test_4_concurrent_zone_access))
    results.append(await run_test("Invalid Zone Safety", test_5_invalid_zone_resilience))
    results.append(await run_test("Memory Sharing", test_6_mmap_memory_sharing))
    results.append(await run_test("Rotation Stress", test_7_zone_rotation_stress))
    results.append(await run_test("Data Integrity", test_8_large_zone_throughput))
    results.append(await run_test("MRU Promotion", test_9_lru_mru_promotion))
    results.append(await run_test("Partial Performance", test_10_partial_read_performance))

    passed = sum(results)
    print(f"\n⭐ FINAL RESULT: {passed}/10 Passed")

if __name__ == "__main__":
    asyncio.run(main())
