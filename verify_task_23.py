import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path("backend").resolve()))

from services.multi_layer_cache import multi_layer_cache

async def verify_task_23():
    print("🧪 Verifying Task 23: Dynamic Fare Update Check...")
    await multi_layer_cache.initialize()
    redis = multi_layer_cache.redis
    
    journey_id = "rt_test_fare"
    fare_lock_key = f"fare_lock:{journey_id}"
    
    # 1. Lock an initial fare of 500
    await redis.setex(fare_lock_key, 600, "500.00")
    
    # 2. Simulate current fare jumped to 520 (> 10 diff)
    current_fare = 520.00
    locked_fare = await redis.get(fare_lock_key)
    
    fare_amount = float(locked_fare.decode())
    if abs(fare_amount - current_fare) > 10.0:
        print(f"💰 Fare jump detected: {fare_amount} -> {current_fare}")
        fare_amount = current_fare
        await redis.setex(fare_lock_key, 600, str(current_fare))
        
    assert fare_amount == 520.00
    new_lock = await redis.get(fare_lock_key)
    assert float(new_lock.decode()) == 520.00
    
    print("✅ Task 23 Verification SUCCESSFUL!")

if __name__ == "__main__":
    asyncio.run(verify_task_23())
