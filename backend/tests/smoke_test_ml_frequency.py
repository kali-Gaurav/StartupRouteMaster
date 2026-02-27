#!/usr/bin/env python3
"""Quick smoke test for ML reliability and frequency-aware Range-RAPTOR"""

import asyncio
from datetime import datetime, date
from ml_reliability_model import MLReliabilityModel
from frequency_aware_range import FrequencyAwareWindowSizer


async def test_ml_reliability():
    """Test ML reliability model"""
    print("\n=== Testing ML Reliability Model ===")
    model = MLReliabilityModel()
    
    # Test fallback heuristic
    reliability = await model.predict(
        trip_id=1,
        origin_stop_id=10,
        destination_stop_id=20,
        departure_time=datetime(2026, 2, 19, 10, 0),
        transfer_duration_minutes=15,
        distance_km=150,
    )
    
    print(f"✓ Reliability prediction: {reliability:.3f}")
    assert 0.0 <= reliability <= 1.0, "Reliability out of range"
    
    # Test with different parameters
    reliability_short = await model.predict(
        trip_id=1,
        origin_stop_id=10,
        destination_stop_id=20,
        departure_time=datetime(2026, 2, 19, 10, 0),
        transfer_duration_minutes=5,  # Very short - should be penalized
        distance_km=150,
    )
    
    print(f"✓ Reliability with short transfer (5 min): {reliability_short:.3f}")
    assert reliability_short < reliability, "Short transfers should reduce reliability"


async def test_frequency_aware():
    """Test frequency-aware window sizing"""
    print("\n=== Testing Frequency-Aware Range-RAPTOR ===")
    sizer = FrequencyAwareWindowSizer()
    
    # Mock the frequency computation to test window sizing
    # Test high frequency
    async def get_window(freq):
        sizer._compute_corridor_frequency = lambda *args: asyncio.coroutine(lambda: freq)()
        return await sizer.get_range_window_minutes(
            origin_stop_id=1,
            destination_stop_id=2,
            search_date=date(2026, 2, 19),
            base_range_minutes=60,
            distance_km=200,
        )
    
    # Note: Direct mocking would be better in real tests; this is simplified
    # The frequency computation would be from the DB in reality
    print("✓ Frequency-aware window sizer instantiated successfully")
    
    # Test with different distances (without needing DB)
    window_short = await sizer.get_range_window_minutes(
        origin_stop_id=1,
        destination_stop_id=2,
        search_date=date(2026, 2, 19),
        distance_km=150,
    )
    print(f"✓ Short distance (150 km) window: {window_short} minutes")
    assert window_short > 0, "Window should be positive"
    
    window_long = await sizer.get_range_window_minutes(
        origin_stop_id=1,
        destination_stop_id=2,
        search_date=date(2026, 2, 19),
        distance_km=1500,
    )
    print(f"✓ Long distance (1500 km) window: {window_long} minutes")
    assert window_long >= window_short, "Long distances should have bigger or equal windows"


async def main():
    print("\n" + "="*60)
    print("SMOKE TEST: ML Reliability + Frequency-Aware Range-RAPTOR")
    print("="*60)
    
    try:
        await test_ml_reliability()
        await test_frequency_aware()
        print("\n" + "="*60)
        print("✅ ALL SMOKE TESTS PASSED")
        print("="*60 + "\n")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
