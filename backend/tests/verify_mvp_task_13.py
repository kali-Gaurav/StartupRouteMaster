import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.route_engine.data_provider import DataProvider

async def verify_task_13():
    print("\n>>> STARTING VERIFICATION: MVP TASK 13 (STALE CACHE PREDICTION)")
    
    provider = DataProvider()
    
    # 1. Test Tier: Tomorrow (5 mins)
    date_tomorrow = datetime.now() + timedelta(hours=12)
    ttl_tomorrow = provider._calculate_dynamic_ttl(date_tomorrow)
    print(f"  Tomorrow (<24h) TTL: {ttl_tomorrow}s")
    assert ttl_tomorrow == 300
    
    # 2. Test Tier: Near Term (15 mins)
    date_near = datetime.now() + timedelta(days=3)
    ttl_near = provider._calculate_dynamic_ttl(date_near)
    print(f"  Near Term (<7d) TTL: {ttl_near}s")
    assert ttl_near == 900
    
    # 3. Test Tier: Long Term (6 hours)
    date_long = datetime.now() + timedelta(days=45)
    ttl_long = provider._calculate_dynamic_ttl(date_long)
    print(f"  Long Term (>30d) TTL: {ttl_long}s")
    assert ttl_long == 21600
    
    # 4. Test Tier: Mid Term (1 hour)
    date_mid = datetime.now() + timedelta(days=15)
    ttl_mid = provider._calculate_dynamic_ttl(date_mid)
    print(f"  Mid Term (15d) TTL: {ttl_mid}s")
    assert ttl_mid == 3600

    print("\n✅ ALL MVP TASK 13 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_13())
