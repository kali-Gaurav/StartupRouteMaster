import asyncio
import random
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from utils.api_monitor import monitor_external_api
from database.session import SessionLocal

@monitor_external_api(provider="RapidAPI", cost_per_call=0.01) # $0.01 per call
async def simulate_rapid_api_call():
    delay = random.uniform(0.1, 1.5)
    await asyncio.sleep(delay)
    if random.random() < 0.1: # 10% error rate
        raise Exception("Simulated RapidAPI Timeout")
    return {"status": "success", "latency": delay}

@monitor_external_api(provider="OpenRouter", cost_per_call=0.005) # $0.005 per call
async def simulate_ai_call():
    delay = random.uniform(0.5, 3.0)
    await asyncio.sleep(delay)
    return {"status": "success", "tokens": 500}

async def run_simulation(count=20):
    print(f"🚀 Starting API Traffic Simulation ({count} calls)...")
    tasks = []
    for _ in range(count):
        tasks.append(simulate_rapid_api_call())
        tasks.append(simulate_ai_call())
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success = len([r for r in results if not isinstance(r, Exception)])
    errors = len([r for r in results if isinstance(r, Exception)])
    print(f"✅ Simulation Complete. Success: {success}, Errors: {errors}")

if __name__ == "__main__":
    asyncio.run(run_simulation())
