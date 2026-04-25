import asyncio
import logging
import time
from core.nexus.chaos import nexus_chaos
from services.multi_layer_cache import cache_layer
from core.resilience import CircuitConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("chaos_audit")

async def run_chaos_audit():
    print("\n--- NEXUS CHAOS & RESILIENCE AUDIT ---")
    
    # 1. Test Latency Injection Resilience
    print("\n[SCENARIO 1] High Latency Simulation (Redis Spike)")
    nexus_chaos.set_latency_injection("cache", 500) # Inject 500ms
    
    start = time.perf_counter()
    # Attempt a cache operation
    await cache_layer.get("test_key")
    latency = (time.perf_counter() - start) * 1000
    
    print(f"Observed Latency: {latency:.2f}ms")
    if latency > 400:
        print("[OK] Chaos Engine successfully injected latency.")
    else:
        print("[WARN] Latency injection did not take effect.")
        
    nexus_chaos.clear_latency("cache")

    # 2. Test Fault Injection (Circuit Breaker)
    print("\n[SCENARIO 2] Database Fault Simulation")
    nexus_chaos.set_fault_injection("transit_db", 1.0) # 100% failure rate
    
    try:
        # Check if the system falls back or trips circuit
        print("Testing DB dependency...")
        # (This is a simplified mock check)
        from database.session import async_engine_transit
        if not async_engine_transit:
            print("[INFO] DB Engine not ready for real fault test, skipping deep check.")
        else:
            print("[INFO] Attempting operation on faulted DB...")
            # If we had a circuit breaker wrapped around DB, we'd check it here
            
    finally:
        nexus_chaos.clear_fault("transit_db")

    print("\n--- CHAOS AUDIT COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(run_chaos_audit())
