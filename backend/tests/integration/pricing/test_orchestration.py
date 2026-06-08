import pytest
import math
import asyncio
from datetime import date, timedelta
from core.pricing.dynamic_engine import dynamic_pricing_engine, PricingStrategy, CompetitorPrice

@pytest.mark.asyncio
async def test_demand_strategy():
    # High fill rate -> Surge
    result = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.0,
        train_number="12345",
        from_station="NDLS",
        to_station="BCT",
        travel_date=date.today() + timedelta(days=15),
        class_code="3A",
        fill_rate=0.9,
        strategy=PricingStrategy.DEMAND_CURVE
    )
    assert result.surge_multiplier > 1.0
    assert result.dynamic_fare > 1000

@pytest.mark.asyncio
async def test_time_decay_strategy():
    # Close to date (1 day) -> Urgency surge
    result = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.0,
        train_number="12345",
        from_station="NDLS",
        to_station="BCT",
        travel_date=date.today() + timedelta(days=1),
        class_code="3A",
        fill_rate=0.7,
        strategy=PricingStrategy.TIME_DECAY
    )
    assert result.surge_multiplier > 1.0
    assert "TIME_DECAY" in result.reasoning

@pytest.mark.asyncio
async def test_yield_strategy():
    # High future demand -> Seat protection
    result = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.0,
        train_number="12345",
        from_station="NDLS",
        to_station="BCT",
        travel_date=date.today() + timedelta(days=10),
        class_code="3A",
        fill_rate=0.8,
        strategy=PricingStrategy.YIELD_MAX
    )
    print(f"Debug: yield_reasoning={result.reasoning}")
    assert "YIELD_MAX" in result.reasoning

@pytest.mark.asyncio
async def test_competitive_strategy():
    competitors = [
        CompetitorPrice(mode="BUS", operator="RedBus", price=800, duration_minutes=600)
    ]
    result = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.0,
        train_number="12345",
        from_station="NDLS",
        to_station="BCT",
        travel_date=date.today() + timedelta(days=10),
        class_code="3A",
        fill_rate=0.5,
        strategy=PricingStrategy.COMPETITIVE,
        competitors=competitors
    )
    # Bus target 680, but floor is 0.7 * 1000 = 700
    print(f"Debug: competitive_fare={result.dynamic_fare}, reasoning={result.reasoning}")
    assert result.dynamic_fare == 700
    assert "COMPETITIVE" in result.reasoning

@pytest.mark.asyncio
async def test_tatkal_premium():
    # 3A Tatkal premium is 30%
    result = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.0,
        train_number="12345",
        from_station="NDLS",
        to_station="BCT",
        travel_date=date.today() + timedelta(days=1),
        class_code="3A",
        fill_rate=0.7,
        is_tatkal=True
    )
    # Base 1000 + 30% = 1300. Then surge if any?
    # Default is DEMAND_CURVE if not specified? 
    # No, it uses working_fare += base_fare * config.tatkal_premium_pct.get(class_code, 0.3)
    print(f"Debug: tatkal_reasoning={result.reasoning}")
    assert "TATKAL" in result.reasoning

@pytest.mark.asyncio
async def test_guardrails():
    # Test Max Surge (1.5x)
    result_max = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.0,
        train_number="12345",
        from_station="NDLS",
        to_station="BCT",
        travel_date=date.today() + timedelta(days=0), # Today
        class_code="3A",
        fill_rate=2.0, # 200% fill
        strategy=PricingStrategy.DEMAND_CURVE
    )
    assert result_max.dynamic_fare <= 1500 # 1000 * 1.5
    assert result_max.surge_multiplier <= 1.5
    
    # Test Min Discount (0.7x)
    result_min = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.0,
        train_number="12345",
        from_station="NDLS",
        to_station="BCT",
        travel_date=date.today() + timedelta(days=30),
        class_code="3A",
        fill_rate=0.0, # 0% fill
        strategy=PricingStrategy.DEMAND_CURVE
    )
    assert result_min.dynamic_fare >= 700 # 1000 * 0.7
    assert result_min.surge_multiplier >= 0.7

@pytest.mark.asyncio
async def test_rounding_and_savings():
    result = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.5,
        train_number="12345",
        from_station="NDLS",
        to_station="BCT",
        travel_date=date.today() + timedelta(days=10),
        class_code="3A",
        fill_rate=0.5,
        strategy=PricingStrategy.DEMAND_CURVE
    )
    # Result should be integer
    assert isinstance(result.dynamic_fare, (int, float))
    assert float(result.dynamic_fare) == float(int(result.dynamic_fare))
    # Savings should be present if dynamic_fare < base_fare
    if result.dynamic_fare < 1000.5:
        assert result.savings_vs_static > 0

@pytest.mark.asyncio
async def test_e2e_pricing_breakdown():
    """Verify integration between DynamicPricingEngine and TaxEngineService."""
    from services.pricing.tax_engine import tax_engine
    
    # 1. Calculate dynamic fare
    result = await dynamic_pricing_engine.calculate_dynamic_fare(
        base_fare=1000.0, train_number="E2E_123",
        from_station="DEL", to_station="MUM",
        travel_date=date.today() + timedelta(days=5),
        class_code="3A", fill_rate=0.8
    )
    
    # 2. Feed dynamic fare into Tax Engine
    breakdown = tax_engine.calculate_breakdown(base_fare=result.dynamic_fare)
    
    # Dynamic fare at 80% fill for 3A (Yield Max) should be around 1100-1200
    # Platform fee is 2% of base_fare (max 150)
    # GST is 18% of platform fee
    
    assert breakdown["base_fare"] == result.dynamic_fare
    assert breakdown["platform_fee"] >= 20.0
    assert breakdown["gst"] == round(breakdown["platform_fee"] * 0.18, 2)
    assert breakdown["total"] == math.ceil(breakdown["base_fare"] + breakdown["platform_fee"] + breakdown["gst"])
    
    print(f"E2E Breakdown: Dynamic Fare: {result.dynamic_fare}, Total with Tax: {breakdown['total']}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_demand_strategy())
    loop.run_until_complete(test_time_decay_strategy())
    loop.run_until_complete(test_yield_strategy())
    loop.run_until_complete(test_competitive_strategy())
    loop.run_until_complete(test_tatkal_premium())
    loop.run_until_complete(test_guardrails())
    loop.run_until_complete(test_rounding_and_savings())
    loop.run_until_complete(test_e2e_pricing_breakdown())
    print("All orchestration tests passed!")
