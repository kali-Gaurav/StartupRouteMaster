import asyncio
import sys
import os
import time
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.external_api_health import rapid_api_health, CircuitState
from core.route_engine.data_provider import DataProvider
from services.multi_layer_cache import multi_layer_cache

async def verify_task_11():
    print("\n>>> STARTING VERIFICATION: MVP TASK 11 (CIRCUIT BREAKER)")
    
    await multi_layer_cache.initialize()
    if not multi_layer_cache.redis:
        print("  REDIS NOT AVAILABLE. SKIPPING.")
        return

    # Reset State for test
    r = multi_layer_cache.redis
    await r.delete(rapid_api_health.key_state, rapid_api_health.key_failures, rapid_api_health.key_last_trip)
    
    print("\n[11.1] Initial State: CLOSED")
    state = await rapid_api_health.get_state()
    assert state == CircuitState.CLOSED
    assert await rapid_api_health.is_available() is True

    # 1. Simulate Failures (Subtask 11.2)
    print("\n[11.2] Simulating 5 consecutive failures...")
    for i in range(5):
        await rapid_api_health.record_failure("Simulated Error")
        
    state = await rapid_api_health.get_state()
    print(f"  Current State: {state}")
    assert state == CircuitState.OPEN
    assert await rapid_api_health.is_available() is False
    print("  SUCCESS: Circuit Tripped to OPEN.")

    # 2. Test Fast Failure in DataProvider (Subtask 11.5)
    print("\n[11.5] Verifying DataProvider skips API call when OPEN...")
    provider = DataProvider()
    # Mock the client to prove it's NOT called
    provider.rapidapi_client = MagicMock()
    provider.rapidapi_client.get_seat_availability = AsyncMock()
    
    res = await provider.verify_seat_availability_unified(1, datetime.now(), "SL", "12625", "NDLS", "KOTA")
    print(f"  Result Source: {res['source']}")
    assert res['source'] == "database_fallback"
    assert provider.rapidapi_client.get_seat_availability.called is False
    print("  SUCCESS: DataProvider correctly bypassed API.")

    # 3. Test Latency-Triggered Trip (Subtask 11.4)
    print("\n[11.4] Testing Latency-triggered trip (Reset first)...")
    await r.delete(rapid_api_health.key_state, rapid_api_health.key_failures)
    
    # Record success with high latency
    await rapid_api_health.record_success(latency_ms=4000) # Limit is 3000
    
    state = await rapid_api_health.get_state()
    print(f"  State after 4s latency: {state}")
    # Threshold is 5 failures, but latency-trip is usually instant or aggregated.
    # In our impl, latency > limit triggers record_failure.
    # So we need 5 high-latency requests to trip.
    for _ in range(4):
        await rapid_api_health.record_success(latency_ms=4000)
        
    state = await rapid_api_health.get_state()
    assert state == CircuitState.OPEN
    print("  SUCCESS: Circuit Tripped due to high latency.")

    # 4. Test Auto-Recovery / Half-Open (Subtask 11.7)
    print("\n[11.7] Testing Recovery to HALF_OPEN...")
    # Mock the last trip time to 10 mins ago
    past_time = time.time() - 600
    await r.set(rapid_api_health.key_last_trip, str(past_time))
    
    state = await rapid_api_health.get_state()
    print(f"  State after cooldown: {state}")
    assert state == CircuitState.HALF_OPEN
    
    # Test successful request in HALF_OPEN
    await rapid_api_health.record_success(latency_ms=100)
    state = await rapid_api_health.get_state()
    print(f"  State after successful test: {state}")
    assert state == CircuitState.CLOSED
    print("  SUCCESS: Circuit recovered to CLOSED.")

    print("\n✅ ALL MVP TASK 11 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_11())
