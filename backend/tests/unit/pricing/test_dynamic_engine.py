import pytest
import math
from core.pricing.dynamic_engine import DemandSupplyCurve, TimeDecaySurge, YieldOptimizer, PricingConfig, CompetitivePricer, CompetitorPrice

def test_demand_multiplier():
    # threshold = 0.7, elasticity = 2.5, amplitude = 0.4
    
    # At threshold, multiplier should be 1.0
    mult = DemandSupplyCurve.calculate_multiplier(0.7)
    assert math.isclose(mult, 1.0, rel_tol=1e-3)
    
    # Below threshold (discount)
    mult_low = DemandSupplyCurve.calculate_multiplier(0.3)
    assert mult_low < 1.0
    
    # Above threshold (surge)
    mult_high = DemandSupplyCurve.calculate_multiplier(0.9)
    assert mult_high > 1.0
    
    # Boundary: 100% fill
    mult_full = DemandSupplyCurve.calculate_multiplier(1.0)
    assert mult_full > 1.1 # Significant surge
    
    # Extrema: 0% fill
    mult_empty = DemandSupplyCurve.calculate_multiplier(0.0)
    assert mult_empty >= 0.6 # Guarded floor by amplitude (1 - 0.4 = 0.6)

def test_class_elasticity():
    assert DemandSupplyCurve.calculate_class_elasticity("SL") > DemandSupplyCurve.calculate_class_elasticity("1A")
    assert DemandSupplyCurve.calculate_class_elasticity("2S") == 3.5 # Most elastic
    assert DemandSupplyCurve.calculate_class_elasticity("FC") == 1.0 # Least elastic

def test_time_decay_surge():
    config = PricingConfig()
    # No surge outside window (10 days)
    assert TimeDecaySurge.calculate_surge(10, 0.8, config) == 1.0
    
    # No surge if fill rate < 0.5
    assert TimeDecaySurge.calculate_surge(2, 0.4, config) == 1.0
    
    # Surge inside window (2 days) with high fill (0.8)
    surge = TimeDecaySurge.calculate_surge(2, 0.8, config)
    assert surge > 1.0
    
    # Urgency peak (1 day)
    peak_surge = TimeDecaySurge.calculate_surge(1, 0.8, config)
    assert peak_surge >= surge

def test_yield_optimizer():
    config = PricingConfig()
    
    # Scarcity premium
    price, reason = YieldOptimizer.calculate_optimal_price(
        base_fare=1000, distance_km=500, fill_rate=0.8,
        remaining_capacity=10, expected_future_demand=30, config=config
    )
    assert price > 1000
    assert "Seat protection" in reason
    
    # Demand stimulation
    price_low, reason_low = YieldOptimizer.calculate_optimal_price(
        base_fare=1000, distance_km=500, fill_rate=0.1,
        remaining_capacity=100, expected_future_demand=10, config=config
    )
    assert price_low < 1000
    assert "Demand stimulation" in reason_low

def test_competitive_pricer():
    config = PricingConfig()
    
    # 1. Bus anchor only
    competitors_bus = [CompetitorPrice(mode="BUS", operator="RedBus", price=800, duration_minutes=600)]
    price_bus, reason_bus = CompetitivePricer.anchor_price(1000, competitors_bus, 600, config)
    assert price_bus == 680
    assert "Bus anchor" in reason_bus
    
    # 2. Flight anchor only
    competitors_flight = [CompetitorPrice(mode="FLIGHT", operator="IndiGo", price=3000, duration_minutes=120)]
    price_flight, reason_flight = CompetitivePricer.anchor_price(500, competitors_flight, 120, config)
    print(f"Debug: price_flight={price_flight}")
    # Target is 1050, but capped at base * 1.1 = 550
    assert price_flight == 550
    assert "Flight anchor" in reason_flight
    
    # 3. Combined (Floor wins)
    competitors_both = competitors_bus + competitors_flight
    price_both, reason_both = CompetitivePricer.anchor_price(1000, competitors_both, 600, config)
    assert price_both == 1050

if __name__ == "__main__":
    # If run directly, just execute them
    test_demand_multiplier()
    test_class_elasticity()
    test_time_decay_surge()
    test_yield_optimizer()
    test_competitive_pricer()
    print("All unit tests passed!")
