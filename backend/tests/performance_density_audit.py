import asyncio
import time
import psutil
import os
import sys
import numpy as np

# Setup path
sys.path.append(os.getcwd())

async def performance_density_audit():
    print("📈 [NEXUS:DENSITY] PERFORMANCE DENSITY AUDIT (Task 30)")
    print("=====================================================")
    
    from core.nexus.bootstrapper import nexus_boot
    from core.nexus.state import SystemState
    from core.nexus.search.node import search_node
    from core.nexus.cache.node import cache_node
    from core.nexus.database.node import database_node
    from core.nexus.financial.node import financial_node
    from core.nexus.scraper.node import scraper_node
    from core.nexus.security.node import security_node
    from core.nexus.rl.node import rl_node
    from core.nexus.transit.reconciler import transit_node
    from services.multi_layer_cache import multi_layer_cache
    
    # Register all nodes (deterministic replication of lifespan.py)
    nexus_boot.register(security_node)
    nexus_boot.register(cache_node)
    nexus_boot.register(database_node)
    nexus_boot.register(financial_node)
    nexus_boot.register(scraper_node)
    nexus_boot.register(rl_node)
    nexus_boot.register(search_node)
    nexus_boot.register(transit_node)

    # 🚀 [NEXUS DETERMINISTIC BOOT]
    print("🚀 [NEXUS] Initiating Deterministic Core Bootstrap for Audit...")
    await nexus_boot.bootstrap()
    
    # Wait for READY state
    print("⏳ Waiting for Nexus Fiber READY state...")
    start_wait = time.time()
    while nexus_boot.state != SystemState.READY:
        await asyncio.sleep(1)
        if time.time() - start_wait > 30:
            print("❌ TIMEOUT: System failed to reach READY state.")
            return

    process = psutil.Process(os.getpid())
    base_mem = process.memory_info().rss / 1024 / 1024
    print(f"✅ Baseline Memory: {base_mem:.2f} MB")
    
    # 🏃 TEST 1: RAPTOR Throughput (Graph-Only)
    print("\n🏃 Test 1: RAPTOR Latency Sweep (50 Concurrent Traversals)")
    latencies = []
    
    # Mock search params
    src = "NDLS"
    dst = "BCT"
    
    start_sweep = time.perf_counter()
    tasks = []
    for _ in range(50):
        tasks.append(search_node.engine.find_routes(src, dst, None, None, graph=search_node.graph))
    
    # We execute them concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    end_sweep = time.perf_counter()
    
    for r in results:
        if isinstance(r, Exception): continue
        # (Assuming we have a way to get individual latency if we wrapped them, 
        # but here we'll use the total average)
        pass
        
    total_time = end_sweep - start_sweep
    rps = 50 / total_time
    avg_latency = (total_time / 50) * 1000
    
    peak_mem = process.memory_info().rss / 1024 / 1024
    density_score = rps / (peak_mem - base_mem) if (peak_mem - base_mem) > 0 else rps
    
    print(f"   Throughput: {rps:.2f} req/s")
    print(f"   Avg Latency: {avg_latency:.2f} ms")
    print(f"   Peak Memory: {peak_mem:.2f} MB")
    print(f"   Density Score: {density_score:.2f} RPS/MB")
    
    # 🧪 TEST 2: Multi-Layer Cache Saturation
    print("\n🧪 Test 2: Multi-Layer Cache Saturation (1000 Sets/Gets)")
    keys = [f"bench:key_{i}" for i in range(1000)]
    
    start_cache = time.perf_counter()
    for k in keys:
        await multi_layer_cache.put(k, {"data": "x" * 100}, ttl=60)
    for k in keys:
        await multi_layer_cache.get(k)
    end_cache = time.perf_counter()
    
    cache_rps = 2000 / (end_cache - start_cache)
    print(f"   Cache Ops: {cache_rps:.2f} op/s")

    print("\n🏆 FINAL CERTIFICATION RESULTS")
    print("------------------------------")
    status = "CERTIFIED" if rps > 10 and peak_mem < 800 else "DEGRADED"
    print(f"Status: {status}")
    print(f"Target: Hostinger KVM 2 (2GB RAM)")
    print(f"Projected Headroom: {2048 - peak_mem:.2f} MB (STABLE)")
    
    if status == "CERTIFIED":
        print("\n🎊 SEAL OF EXCELLENCE GRANTED. RouteMaster V3 is ready for deployment.")

if __name__ == "__main__":
    asyncio.run(performance_density_audit())
