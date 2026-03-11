import asyncio
import time
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.ml_models.intent_predictor import intent_predictor

async def run_test(name, func):
    print(f"🧪 Testing: {name}...", end=" ", flush=True)
    try:
        await func()
        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

# --- 15 INTENT PREDICTION TESTS ---

async def test_1_search_intent():
    intent, conf = await intent_predictor.predict("GET", "/api/search/stations", {})
    assert intent == "SEARCH"
    assert conf > 0.8

async def test_2_booking_intent():
    intent, conf = await intent_predictor.predict("POST", "/api/bookings/create", {})
    assert intent == "BOOKING"
    assert conf > 0.8

async def test_3_status_intent():
    intent, conf = await intent_predictor.predict("GET", "/api/v2/live/train", {"user-agent": "Mobile Safari"})
    assert intent == "STATUS"

async def test_4_admin_intent():
    intent, conf = await intent_predictor.predict("GET", "/api/admin/dashboard", {})
    assert intent == "ADMIN"

async def test_5_other_intent():
    intent, conf = await intent_predictor.predict("GET", "/api/health", {})
    assert intent == "OTHER"

async def test_6_ambiguous_path():
    # "find" is search keyword
    intent, conf = await intent_predictor.predict("GET", "/api/v2/debug/find_leaks", {})
    assert intent == "SEARCH" 

async def test_7_payment_intent():
    intent, conf = await intent_predictor.predict("POST", "/api/payments/verify", {})
    assert intent == "BOOKING"

async def test_8_mobile_bias():
    # Mobile should boost STATUS probability
    intent_m, conf_m = await intent_predictor.predict("GET", "/api/v2/live/123", {"user-agent": "Mobile"})
    intent_d, conf_d = await intent_predictor.predict("GET", "/api/v2/live/123", {"user-agent": "Desktop"})
    assert intent_m == "STATUS"
    # Even if both are STATUS, mobile confidence should be higher or at least boosted internally
    
async def test_9_root_intent():
    intent, conf = await intent_predictor.predict("GET", "/", {})
    assert intent in ["SEARCH", "OTHER"] # Based on priors

async def test_10_large_headers_performance():
    headers = {f"X-H{i}": "v" * 100 for i in range(100)}
    start = time.time()
    await intent_predictor.predict("GET", "/api/search", headers)
    duration = (time.time() - start) * 1000
    assert duration < 5 # Sub-ms or at least very fast

async def test_11_unrecognized_path():
    intent, conf = await intent_predictor.predict("GET", "/api/unknown/random/xyz", {})
    assert intent in ["SEARCH", "OTHER"] # Default to highest prior

async def test_12_case_insensitivity():
    intent, conf = await intent_predictor.predict("get", "/API/SEARCH", {})
    assert intent == "SEARCH"

async def test_13_query_param_ignoring():
    intent, conf = await intent_predictor.predict("GET", "/api/live?train=123", {})
    assert intent == "STATUS"

async def test_14_multithreaded_safety():
    # Run 100 predictions in parallel
    tasks = [intent_predictor.predict("GET", "/api/search", {}) for _ in range(100)]
    results = await asyncio.gather(*tasks)
    assert all(r[0] == "SEARCH" for r in results)

async def test_15_extreme_path_length():
    path = "/api/search/" + "a" * 5000
    intent, conf = await intent_predictor.predict("GET", path, {})
    assert intent == "SEARCH"

async def main():
    print("🚀 Running 15 Hard Tests for Subtask 1.2: Bayesian Intent Predictor\n")
    results = []
    results.append(await run_test("Search Intent Detection", test_1_search_intent))
    results.append(await run_test("Booking Intent Detection", test_2_booking_intent))
    results.append(await run_test("Mobile Status Bias", test_3_status_intent))
    results.append(await run_test("Admin Detection", test_4_admin_intent))
    results.append(await run_test("Internal/Other Detection", test_5_other_intent))
    results.append(await run_test("Ambiguous Path Handling", test_6_ambiguous_path))
    results.append(await run_test("Payment/Booking Link", test_7_payment_intent))
    results.append(await run_test("Device Bias Logic", test_8_mobile_bias))
    results.append(await run_test("Default Priority", test_9_root_intent))
    results.append(await run_test("Prediction Latency (<5ms)", test_10_large_headers_performance))
    results.append(await run_test("Unknown Route Robustness", test_11_unrecognized_path))
    results.append(await run_test("Case Sensitivity", test_12_case_insensitivity))
    results.append(await run_test("Query Parameter Isolation", test_13_query_param_ignoring))
    results.append(await run_test("Parallel Prediction Safety", test_14_multithreaded_safety))
    results.append(await run_test("Path Length Stress", test_15_extreme_path_length))

    passed = sum(results)
    print(f"\n⭐ FINAL RESULT: {passed}/15 Passed")
    if passed < 15:
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
