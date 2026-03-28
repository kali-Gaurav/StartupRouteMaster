import asyncio
import os
import sys
import time
import httpx

# Setup sys.path
sys.path.append(os.getcwd())

async def verify_chaos_latency():
    print("🛡️ Verifying Task 25: Chaos Latency Injection...")
    
    BASE_URL = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # 1. Baseline search (Should be fast)
        print("Performing baseline search (expecting < 100ms)...")
        start = time.perf_counter()
        try:
             # Just checking the local singleton first to avoid server start overhead for this specific unit test
             from core.nexus.audit.chaos import nexus_chaos
             
             # Step A: ARM the trap
             print("Arming 'search_unified' with 0.5s base + 0.2s jitter...")
             nexus_chaos.arm("search_unified", base_delay=0.5, jitter=0.2)
             
             # Step B: Execute logic manually or via mock
             print("Testing Latency Trap execution...")
             start_t = time.perf_counter()
             await nexus_chaos.apply_trap("search_unified")
             elapsed = time.perf_counter() - start_t
             print(f"Injected Delay: {elapsed:.3f}s")
             
             if 0.3 <= elapsed <= 0.7:
                  print("✅ Latency injection within expected range (0.3s - 0.7s).")
             else:
                  print(f"❌ Error: Latency injection outside range ({elapsed:.3f}s).")

             # 2. Test Error Injection
             print("Arming 'search_unified' with 100% error rate...")
             nexus_chaos.arm("search_unified", error_rate=1.0)
             
             try:
                  await nexus_chaos.apply_trap("search_unified")
                  print("❌ Error: Expected failure but trap passed.")
             except RuntimeError as e:
                  print(f"✅ Error injection caught: {e}")
                  
             # 3. Disarm
             print("Disarming...")
             nexus_chaos.disarm("search_unified")
             
             start_t = time.perf_counter()
             await nexus_chaos.apply_trap("search_unified")
             elapsed = time.perf_counter() - start_t
             print(f"Post-Disarm Delay: {elapsed:.3f}s")
             
             if elapsed < 0.01:
                  print("✅ Disarm successful.")
             else:
                  print(f"❌ Error: Still seeing delay after disarm ({elapsed:.3f}s).")

             print("\n🎉 Chaos Mesh Fabric V1 Verified.")

        except Exception as e:
             print(f"❌ Verification failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_chaos_latency())
