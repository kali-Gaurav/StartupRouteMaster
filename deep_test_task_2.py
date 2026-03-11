import asyncio
import logging
import time
import os
import sys

# Add backend to sys.path to allow importing backend modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.multi_layer_cache import multi_layer_cache
from core.route_engine.data_provider import DataProvider
from utils.external_api_health import rapid_api_health, rappid_health, CircuitState
from utils.http_client import HttpClientManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_deep_test_task_2():
    print("\n🚀 [DEEP TEST TASK 2] API Resiliency & AsyncIO Hardening\n")
    errors = []
    
    # Initialize cache and http client for testing
    await multi_layer_cache.initialize()
    await HttpClientManager.get_session()
    
    dp = DataProvider()
    
    try:
        # --- TEST 1: Circuit Breaker State Transitions (Subtasks 2.4, 2.17) ---
        print("🔍 [TEST 1/5] Circuit Breaker Logic & Transitions...")
        # Reset state
        await rapid_api_health._set_state(CircuitState.CLOSED)
        if await rapid_api_health.get_state() != CircuitState.CLOSED:
            errors.append("Circuit Breaker failed to reset to CLOSED.")
        
        # Simulate failures to trip breaker
        for _ in range(rapid_api_health.failure_threshold):
            await rapid_api_health.record_failure("Simulated Error")
            
        state = await rapid_api_health.get_state()
        if state != CircuitState.OPEN:
            errors.append(f"Circuit Breaker failed to trip to OPEN after {rapid_api_health.failure_threshold} failures. State is {state}")
        
        # Force Half-Open transition by manipulating last_trip time in Redis
        r = await rapid_api_health._get_redis()
        if r:
            await r.set(rapid_api_health.key_last_trip, str(time.time() - rapid_api_health.recovery_timeout - 10))
            state = await rapid_api_health.get_state()
            if state != CircuitState.HALF_OPEN:
                errors.append(f"Circuit Breaker failed to transition to HALF_OPEN after timeout. State is {state}")
            
            # Simulate a successful request in HALF_OPEN to close it
            await rapid_api_health.record_success(latency_ms=100)
            state = await rapid_api_health.get_state()
            if state != CircuitState.CLOSED:
                errors.append(f"Circuit Breaker failed to transition from HALF_OPEN to CLOSED on success. State is {state}")
        else:
            print("⚠️ Skipping state transition test (Redis not available).")


        # --- TEST 2: DataProvider None/Error Handling (Subtasks 2.9, 2.18) ---
        print("🔍 [TEST 2/5] DataProvider Graceful Fallbacks...")
        # Temporarily mock the rapidapi client to force a None response
        if dp.rapidapi_client:
            original_get_seat = dp.rapidapi_client.get_seat_availability
            dp.rapidapi_client.get_seat_availability = lambda *args, **kwargs: asyncio.sleep(0.1) # Returns None implicitly
            
            res = await dp.verify_seat_availability_unified(
                trip_id=1, travel_date=datetime.now(), train_number="12345", 
                from_station="NDLS", to_station="MMCT"
            )
            
            if res.get("source") != "database_fallback_null":
                errors.append(f"DataProvider failed to fallback to DB on None RapidAPI response. Got: {res}")
                
            # Restore original
            dp.rapidapi_client.get_seat_availability = original_get_seat
        else:
            print("⚠️ Skipping DataProvider None test (RapidAPI client not configured).")


        # --- TEST 3: AsyncIO Concurrency & Connection Limits (Subtasks 2.8, 2.11) ---
        print("🔍 [TEST 3/5] Concurrent Batch Processing...")
        # Test batch seat verification logic
        queries = [
            {"train_number": f"100{i}", "from_station": "A", "to_station": "B", "date": "2026-10-10", "quota": "GN"}
            for i in range(12)
        ]
        
        start = time.perf_counter()
        results = await dp.verify_seat_availability_batch(queries)
        dur = time.perf_counter() - start
        
        if len(results) != 12:
            errors.append(f"Batch processing returned {len(results)} results, expected 12.")
        print(f"   Processed {len(queries)} simulated concurrent lookups in {dur:.2f}s")


        # --- TEST 4: Global HTTP Session Integrity (Subtasks 2.1, 2.2, 2.13) ---
        print("🔍 [TEST 4/5] Singleton HTTP Session Validation...")
        session1 = await HttpClientManager.get_session()
        session2 = await HttpClientManager.get_session()
        
        if session1 is not session2:
            errors.append("HttpClientManager is creating multiple sessions instead of a singleton!")
            
        if "RouteMaster-Production" not in session1.headers.get("User-Agent", ""):
            errors.append("Standardized User-Agent missing from global session.")


        # --- TEST 5: API Key Rotation Validation (Subtask 2.19) ---
        print("🔍 [TEST 5/5] API Key Rotation Engine...")
        from services.booking.rapid_api_client import RapidAPIClient
        # Initialize a temporary client with multiple keys
        multi_key_client = RapidAPIClient("key1,key2,key3", max_concurrent=2)
        
        h1 = multi_key_client._get_current_headers()
        h2 = multi_key_client._get_current_headers()
        h3 = multi_key_client._get_current_headers()
        h4 = multi_key_client._get_current_headers()
        
        if h1["x-rapidapi-key"] != "key1" or h2["x-rapidapi-key"] != "key2" or \
           h3["x-rapidapi-key"] != "key3" or h4["x-rapidapi-key"] != "key1":
            errors.append("API key rotation logic failed to cycle through keys correctly.")
            
    except Exception as e:
        errors.append(f"Unhandled exception during deep test: {str(e)}")
        logger.exception("Test crashed")
        
    finally:
        # Cleanup
        dp.close()
        await HttpClientManager.close_session()
        if multi_layer_cache.redis:
            await multi_layer_cache.redis.close()

    print("\n" + "="*40)
    if not errors:
        print("✅ ALL DEEP TESTS FOR TASK 2 PASSED! System is robust.")
    else:
        print(f"❌ FAILED with {len(errors)} errors:")
        for e in errors: print(f"  - {e}")
    print("="*40)

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(run_deep_test_task_2())
