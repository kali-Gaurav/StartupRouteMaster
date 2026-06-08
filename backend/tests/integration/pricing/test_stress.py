import pytest
import asyncio
import time
from datetime import date, timedelta
from core.pricing.dynamic_engine import dynamic_pricing_engine

@pytest.mark.asyncio
async def test_stress_concurrent_pricing():
    num_requests = 1000
    tasks = []
    
    start = time.time()
    for i in range(num_requests):
        tasks.append(dynamic_pricing_engine.calculate_dynamic_fare(
            base_fare=1000.0, train_number=f"STRESS_{i}",
            from_station="A", to_station="B",
            travel_date=date.today() + timedelta(days=10),
            class_code="3A", fill_rate=0.5
        ))
    
    results = await asyncio.gather(*tasks)
    duration = time.time() - start
    req_per_sec = num_requests / duration
    
    print(f"Stress Test: Processed {num_requests} requests in {duration:.2f}s ({req_per_sec:.2f} req/sec)")
    assert req_per_sec > 100 # Low bar for single-threaded python, but good for base validation

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(stress_test_concurrent_pricing())
    print("Stress test passed!")
