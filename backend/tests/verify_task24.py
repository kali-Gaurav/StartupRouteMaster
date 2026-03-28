import asyncio
import os
import sys
import tracemalloc

# Setup sys.path
sys.path.append(os.getcwd())

async def verify_mem_profiler():
    print("🛡️ Verifying Task 24: Memory Leak Profiler...")
    
    from core.nexus.audit.mem_profiler import mem_profiler
    mem_profiler.LEAK_GROWTH_THRESHOLD_MB = 0.05 # Lower threshold to 50KB for testing
    
    mem_profiler.start()
    
    # 1. Take initial snapshot
    print("Baseline Snapshot...")
    await mem_profiler.take_snapshot()
    
    # 2. Simulate a "Leak" (e.g. accumulating lots of strings)
    print("Simulating Leak...")
    leak_source = []
    for i in range(10000):
        leak_source.append(f"LEAK_DATA_STRING_{i}_" * 10)
        
    # 3. Take second snapshot
    print("Final Snapshot...")
    result = await mem_profiler.take_snapshot()
    
    print(f"Analysis: {result}")
    
    stats = mem_profiler.get_stats()
    print(f"Stats: {stats}")
    
    if stats['leak_incidents'] > 0:
        print("✅ Memory Leak detected successfully.")
    else:
        print("❌ Error: Memory Leak NOT detected.")
        
    # 4. Dashboard Integration
    # Need mock bootstrapper if not running in full context
    from core.nexus.bootstrapper import nexus_boot
    vitals = nexus_boot.profiler.get_stats()
    print(f"Dashboard Stats: {vitals}")
    
    mem_profiler.stop()

if __name__ == "__main__":
    asyncio.run(verify_mem_profiler())
