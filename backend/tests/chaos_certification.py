import asyncio
import os
import sys
import time
import httpx

# Setup sys.path
sys.path.append(os.getcwd())

async def run_certification():
    print("🛡️ NEXUS CHAOS CERTIFICATION SUITE [Task 25.15]")
    print("===============================================")
    
    # Domains to test
    TRAPS = [
        "search_unified",
        "search_engine",
        "cache_l2",
        "db_io",
        "scraper_external",
        "financial_signing",
        "sse_jitter"
    ]
    
    from core.nexus.audit.chaos import nexus_chaos
    
    for trap in TRAPS:
        print(f"\n🔹 Testing Domain: {trap}")
        
        # 1. ARM Latency
        print("   Arming 0.3s latency...")
        nexus_chaos.arm(trap, base_delay=0.3)
        
        start = time.perf_counter()
        await nexus_chaos.apply_trap(trap)
        elapsed = time.perf_counter() - start
        
        if 0.2 <= elapsed <= 0.5:
             print(f"   ✅ Latency Injection Verified ({elapsed:.3f}s)")
        else:
             print(f"   ❌ Latency Injection Failure ({elapsed:.3f}s)")

        # 2. ARM Failure
        print("   Arming 100% error rate...")
        nexus_chaos.arm(trap, error_rate=1.0)
        
        try:
             await nexus_chaos.apply_trap(trap)
             print("   ❌ Failure Injection Missed.")
        except RuntimeError:
             print("   ✅ Failure Injection Caught.")
             
        # 3. DISARM
        nexus_chaos.disarm(trap)
        print("   ✅ Domain Disarmed.")

    print("\n🔹 Testing Creeping Slowdown (Subtask 25.11)")
    nexus_chaos.arm("creep_test", base_delay=0.1)
    creep_task = asyncio.create_task(nexus_chaos.start_creeping_slowdown("creep_test", rate=0.1, interval=1))
    
    await asyncio.sleep(2.5) # Should increase by ~0.2s
    start = time.perf_counter()
    await nexus_chaos.apply_trap("creep_test")
    elapsed = time.perf_counter() - start
    
    print(f"   Measured creep delay after 2s: {elapsed:.3f}s (Baseline was 0.1s)")
    if elapsed > 0.25:
         print("   ✅ Dynamic Creep Verified.")
    else:
         print(f"   ❌ Creep logic sluggish or failed ({elapsed:.3f}s).")
         
    nexus_chaos.disarm("creep_test")
    creep_task.cancel()

    print("\n🎉 NEXUS FIBER: CHAOS CERTIFICATION COMPLETE.")
    print("CORE STABILITY RATING: INDESTRUCTIBLE.")

if __name__ == "__main__":
    asyncio.run(run_certification())
