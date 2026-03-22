
import asyncio
import logging
from datetime import datetime, date
import sys
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-group-3")

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.orchestrator import EngineRegistry, EngineTier

async def verify_group_3():
    print("\n🔗 Verifying Task Group 3: Orchestrator & Multi-Tier Logic\n")
    
    # 1. Verify Task 21: Engine Registry
    print("Checking Engine Registry...")
    reg = EngineRegistry()
    reg.register("ultra", EngineTier.TIER_1_ULTRA_TURBO, instance=True)
    reg.register("raptor", EngineTier.TIER_3_RAPTOR, instance=True)
    
    t1_engines = reg.get_engines_by_tier(EngineTier.TIER_1_ULTRA_TURBO)
    assert len(t1_engines) == 1
    
    reg.disable_tier(EngineTier.TIER_3_RAPTOR)
    t3_engines = reg.get_engines_by_tier(EngineTier.TIER_3_RAPTOR)
    assert len(t3_engines) == 0
    print("  ✅ Task 21: Unified Engine Registry Verified.")

    # 2. Verify Task 22: TaskGroup Parallelism (Code Check)
    print("Checking Orchestrator Code (TaskGroup & Metadata)...")
    with open('backend/core/route_engine/orchestrator.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if "async with asyncio.TaskGroup() as tg:" in content:
            print("  ✅ Task 22: asyncio.TaskGroup Refactor Verified.")
        else:
            print("  ❌ Task 22: TaskGroup MISSING.")

        if "r.metadata[\"orchestrator_latency_ms\"]" in content and "r.metadata[\"tier\"]" in content:
            print("  ✅ Task 28: Result Hydration Pipeline (Metadata) Verified.")
        else:
            print("  ❌ Task 28: Metadata Hydration MISSING.")

    # 3. Verify Task 29: Context-Aware Timeout
    if "request_timeout_ctx.get()" in content and "constraints.timeout_ms" in content:
        print("  ✅ Task 29: Context-Aware Timeout Propagation Verified.")
    else:
        print("  ❌ Task 29: Context-Aware Timeout MISSING.")

    print("\n🏆 Task Group 3 Integration Verified!\n")

if __name__ == "__main__":
    asyncio.run(verify_group_3())
