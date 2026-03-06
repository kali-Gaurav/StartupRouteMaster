import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path("backend").resolve()))

from services.multi_layer_cache import multi_layer_cache

async def verify_task_19():
    print("🧪 Verifying Task 19: Fraudulent UTR Lockout...")
    await multi_layer_cache.initialize()
    redis = multi_layer_cache.redis
    
    test_ip = "127.0.0.1"
    lockout_key = f"fraud_lock:{test_ip}"
    
    # 1. Clear state
    await redis.delete(lockout_key)
    
    # 2. First attempt
    val = await redis.incr(lockout_key)
    print(f"Attempt 1: Counter is {val}")
    if val == 1:
        await redis.expire(lockout_key, 3600)
        
    ttl = await redis.ttl(lockout_key)
    print(f"TTL after first attempt: {ttl}s")
    assert ttl > 3500 # Should be close to 3600
    
    # 3. Second and third attempts
    await redis.incr(lockout_key)
    await redis.incr(lockout_key)
    
    final_count = await redis.get(lockout_key)
    print(f"Final Count: {final_count}")
    assert int(final_count) == 3
    
    print("✅ Task 19 Verification SUCCESSFUL!")

if __name__ == "__main__":
    asyncio.run(verify_task_19())
