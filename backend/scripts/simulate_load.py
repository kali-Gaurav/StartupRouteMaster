import asyncio
import aiohttp
import time
import random

async def simulate_search(session, src, dst):
    url = f"http://localhost:8000/api/v2/search/unified?source={src}&destination={dst}&date=2026-03-04"
    start = time.perf_counter()
    async with session.get(url) as response:
        status = response.status
        data = await response.json()
        dur = (time.perf_counter() - start) * 1000
        print(f"Search {src}->{dst}: {status} in {dur:.2f}ms (Throttled: {data.get('is_throttled')})")

async def main():
    print("🚀 Starting Load Simulation...")
    async with aiohttp.ClientSession() as session:
        tasks = []
        # Simulate 20 rapid searches
        pairs = [("NDLS", "MAS"), ("BCT", "HWH"), ("MAS", "SBC"), ("NDLS", "PNBE")]
        for _ in range(20):
            src, dst = random.choice(pairs)
            tasks.append(simulate_search(session, src, dst))
            # Tiny delay to simulate real users
            await asyncio.sleep(0.1)
        
        await asyncio.gather(*tasks)
    print("✅ Simulation Finished.")

if __name__ == "__main__":
    asyncio.run(main())
