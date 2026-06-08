import pytest
import asyncio
import time
from datetime import date, timedelta
from core.pricing.dynamic_engine import dynamic_pricing_engine, PricingStrategy

@pytest.mark.asyncio
async def test_price_cache_ttl():
    # 1. First call
    start_time = time.time()
    result1 = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.0, train_number="CACHE_TEST",
        from_station="A", to_station="B",
        travel_date=date.today() + timedelta(days=10),
        class_code="3A", fill_rate=0.5
    )
    
    # 2. Second call (should be cached)
    result2 = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.0, train_number="CACHE_TEST",
        from_station="A", to_station="B",
        travel_date=date.today() + timedelta(days=10),
        class_code="3A", fill_rate=0.5
    )
    
    # Ensure they are the same object or identical results
    assert result1.dynamic_fare == result2.dynamic_fare
    assert result1.reasoning == result2.reasoning

@pytest.mark.asyncio
async def test_unlock_fee_complexity():
    # 1 segment, total fare 1000 -> 10.0 (below 10% cap)
    fee1 = dynamic_pricing_engine.calculate_unlock_fee(total_dynamic_fare=1000, num_segments=1)
    assert fee1 == 10.0
    
    # 3 segments, total fare 1000 -> 50.0 (below 10% cap)
    fee2 = dynamic_pricing_engine.calculate_unlock_fee(total_dynamic_fare=1000, num_segments=3)
    assert fee2 == 50.0
    
    # 3 segments, deep search, total fare 400 -> 40.0 (capped by 10% of 400)
    # base fee = 50 + 25 = 75. 10% of 400 = 40.
    fee3 = dynamic_pricing_engine.calculate_unlock_fee(total_dynamic_fare=400, num_segments=3, is_deep_search=True)
    assert fee3 == 40.0

@pytest.mark.asyncio
async def test_price_route_performance():
    class MockSegment:
        def __init__(self, train_number, distance_km):
            self.train_number = train_number
            self.distance_km = distance_km
            self.departure_time = date.today() + timedelta(days=5)
            self.departure_code = "DEP"
            self.arrival_code = "ARR"
            
    class MockRoute:
        def __init__(self, segments):
            self.segments = segments
            
    segments = [MockSegment(f"T{i}", 100) for i in range(10)]
    route = MockRoute(segments)
    
    # Warm up (includes lazy imports)
    await dynamic_pricing_engine.price_route(route, class_code="SL")
    
    start = time.time()
    results = await dynamic_pricing_engine.price_route(route, class_code="SL")
    duration = (time.time() - start) * 1000 # ms
    
    assert len(results) == 10
    print(f"Performance: 10 segments priced in {duration:.2f}ms (Warm Cache)")
    assert duration < 50, f"Performance target failed: {duration:.2f}ms > 50ms"

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_price_cache_ttl())
    loop.run_until_complete(test_unlock_fee_complexity())
    loop.run_until_complete(test_price_route_performance())
    print("All performance and integration tests passed!")
