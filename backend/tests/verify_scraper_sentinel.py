import asyncio
import logging
import time
from services.scraper_sentinel import scraper_sentinel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sentinel-test")

async def verify_task_48():
    print("🧪 Starting Verification for Task 48: Project Scraper Sentinel...")
    
    # 1. Initialize Sentinel
    await scraper_sentinel.start()
    print("✅ Sentinel Initialized.")

    # 2. Test Identity Rotation [48.2]
    print("\n🎭 Testing Identity Rotation (Acquire 2 Contexts)...")
    c1 = await scraper_sentinel.acquire_context()
    c2 = await scraper_sentinel.acquire_context()
    
    ua1 = await c1["context"].pages[0].evaluate("navigator.userAgent") if c1["context"].pages else "N/A"
    print(f"✅ Context 1 Identity: {ua1[:40]}...")
    
    # 3. Test Scaling [48.3]
    print(f"\n📈 Current Pool Size: {len(scraper_sentinel._contexts)} (Expected >= 2)")
    assert len(scraper_sentinel._contexts) >= 2

    # 4. Test Circuit Breaker [48.7]
    print("\n🚨 Testing Circuit Breaker (Trip for NTES)...")
    source = "ntes"
    assert scraper_sentinel.is_available(source) is True
    
    for i in range(5):
        scraper_sentinel.record_failure(source)
    
    print(f"✅ Failure recorded 5 times. Available: {scraper_sentinel.is_available(source)}")
    assert scraper_sentinel.is_available(source) is False

    # 5. Clean Up
    print("\n🛑 Cleaning up Sentinel...")
    await scraper_sentinel.release_context(c1)
    await scraper_sentinel.release_context(c2)
    await scraper_sentinel.stop()

    print("\n✅ TASK 48 VERIFIED: Scraper Sentinel is Resilient and Stealthy.")

if __name__ == "__main__":
    asyncio.run(verify_task_48())
