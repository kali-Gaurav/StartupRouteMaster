import asyncio
import time
import httpx
import random
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("load-sim")

BASE_URL = "http://localhost:8000/api/v3"

async def simulate_search_traffic(fingerprint: str, intensity: int):
    """
    Simulates a burst of search traffic from a single device.
    Used to test Sentinel S1.5 Velocity Latching.
    """
    async with httpx.AsyncClient() as client:
        for i in range(intensity):
            start = time.perf_counter()
            try:
                # Random routes to test entropy
                source = random.choice(["NDLS", "BCT", "MAS", "HWH"])
                dest = random.choice(["PNBE", "LKO", "JP", "ADI"])
                
                response = await client.post(
                    f"{BASE_URL}/search",
                    params={"source": source, "destination": dest, "date": "2026-04-25", "tier": "BASIC"},
                    headers={"User-Agent": f"LoadSim-Bot-{fingerprint}", "X-Track-IP": f"192.168.1.{random.randint(1,255)}"}
                )
                latency = (time.perf_counter() - start) * 1000
                logger.info(f"[{fingerprint}] Request {i+1}: {response.status_code} | Latency: {latency:.2f}ms")
                
                if response.status_code == 403:
                    logger.warning(f"🛑 [LOCKED] Sentinel blocked the device at request {i+1}")
                    break
                    
            except Exception as e:
                logger.error(f"Error: {e}")
            
            # Tiny jitter to simulate realistic scraper
            await asyncio.sleep(random.uniform(0.1, 0.5))

async def main():
    """
    Industrial Load Simulation:
    1. Normal User (Low velocity, Low entropy)
    2. Scraper Bot (High velocity, High entropy)
    """
    logger.info("🚀 Starting Industrial Load Simulation...")
    
    # 1. Normal User (Simulate 5 requests)
    await simulate_search_traffic("normal-user-id", 5)
    
    # 2. Aggressive Scraper (Simulate 50 requests)
    await simulate_search_traffic("aggressive-scraper-id", 50)

if __name__ == "__main__":
    asyncio.run(main())
