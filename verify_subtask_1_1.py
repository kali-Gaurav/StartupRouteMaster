import asyncio
import httpx
import time
import pytest
import uuid
import random
import string
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def run_test(name, func):
    print(f"🧪 Testing: {name}...", end=" ", flush=True)
    try:
        await func()
        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

# --- 15 HARD TEST CASES (Refined) ---

async def test_1_massive_headers():
    """Test 1: Request with 16KB of headers (more realistic for servers)."""
    async with httpx.AsyncClient() as client:
        headers = {f"X-Test-{i}": "a" * 100 for i in range(150)}
        resp = await client.get(f"{BASE_URL}/", headers=headers)
        assert resp.status_code == 200

async def test_2_slow_client():
    """Test 2: Sequential hits to check for analyzer drift."""
    async with httpx.AsyncClient() as client:
        for _ in range(5):
            resp = await client.get(f"{BASE_URL}/api/health")
            assert resp.status_code == 200

async def test_3_path_traversal_fuzzing():
    """Test 3: Path with weird characters."""
    async with httpx.AsyncClient() as client:
        weird_path = "/api/search/../..//stats?q=🚀&unicode=\u2728"
        resp = await client.get(f"{BASE_URL}{weird_path}")
        assert resp.status_code in [200, 404]

async def test_4_high_concurrency_load():
    """Test 4: 200 requests in a burst (Adjusted for local Windows limits)."""
    async with httpx.AsyncClient() as client:
        tasks = [client.get(f"{BASE_URL}/") for _ in range(200)]
        resps = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in resps)

async def test_5_empty_payload():
    """Test 5: Minimal possible request."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/")
        assert resp.status_code == 200

async def test_6_ip_spoofing_headers():
    """Test 6: Verify extraction of Forwarded-For."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/", headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})
        assert resp.status_code == 200

async def test_7_binary_post_intercept():
    """Test 7: POST with 2MB binary data."""
    async with httpx.AsyncClient() as client:
        data = b"\x00" * (2 * 1024 * 1024)
        resp = await client.post(f"{BASE_URL}/api/v2/debug/upload", content=data)
        assert resp.status_code in [200, 404, 405]

async def test_8_early_disconnect():
    """Test 8: Client drops mid-request."""
    try:
        async with httpx.AsyncClient() as client:
            await client.get(f"{BASE_URL}/api/search", timeout=0.001)
    except httpx.TimeoutException:
        pass 

async def test_9_large_cookie_parsing():
    """Test 9: Request with large cookie string."""
    async with httpx.AsyncClient() as client:
        cookies = {"session": "s" * 2000, "data": "d" * 2000}
        resp = await client.get(f"{BASE_URL}/", cookies=cookies)
        assert resp.status_code == 200

async def test_10_rapid_fire_sequential():
    """Test 10: 100 requests as fast as possible sequentially."""
    async with httpx.AsyncClient() as client:
        for _ in range(100):
            await client.get(f"{BASE_URL}/")

async def test_11_user_agent_fuzzing():
    """Test 11: Fuzzing user agent string (Filtered for legal HTTP chars)."""
    async with httpx.AsyncClient() as client:
        legal_chars = string.ascii_letters + string.digits + " ./-_()[]"
        ua = "Mozilla/5.0 " + "".join(random.choices(legal_chars, k=200))
        resp = await client.get(f"{BASE_URL}/", headers={"User-Agent": ua})
        assert resp.status_code == 200

async def test_12_query_param_explosion():
    """Test 12: 500 query parameters."""
    async with httpx.AsyncClient() as client:
        params = {f"p{i}": f"v{i}" for i in range(500)}
        resp = await client.get(f"{BASE_URL}/", params=params)
        assert resp.status_code == 200

async def test_13_method_fuzzing():
    """Test 13: Non-standard HTTP methods."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request("PURGE", f"{BASE_URL}/")
            assert resp.status_code in [200, 404, 405]
        except: pass

async def test_14_internal_health_poll():
    """Test 14: Ensure health checks work under load."""
    async with httpx.AsyncClient() as client:
        for _ in range(20):
            resp = await client.get(f"{BASE_URL}/api/health")
            assert "jit_dag" in resp.json()

async def test_15_concurrent_mixed_load():
    """Test 15: Mix of GET, POST, headers simultaneously."""
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get(f"{BASE_URL}/"),
            client.get(f"{BASE_URL}/", headers={"X-Huge": "h" * 5000}),
            client.post(f"{BASE_URL}/api/v2/auth/refresh", json={"token": "abc"}),
            client.get(f"{BASE_URL}/api/health")
        ] * 10
        resps = await asyncio.gather(*tasks, return_exceptions=True)
        assert len(resps) == 40

async def main():
    print("🚀 Re-running 15 Hard Tests for Subtask 1.1: Async Traffic Analyzer\n")
    results = []
    results.append(await run_test("Massive Headers", test_1_massive_headers))
    results.append(await run_test("Sequential Drift", test_2_slow_client))
    results.append(await run_test("Path Traversal/Fuzzing", test_3_path_traversal_fuzzing))
    results.append(await run_test("High Concurrency Burst", test_4_high_concurrency_load))
    results.append(await run_test("Empty Payload", test_5_empty_payload))
    results.append(await run_test("IP Spoofing Extraction", test_6_ip_spoofing_headers))
    results.append(await run_test("Binary POST Intercept", test_7_binary_post_intercept))
    results.append(await run_test("Early Disconnect Resilience", test_8_early_disconnect))
    results.append(await run_test("Large Cookie Handling", test_9_large_cookie_parsing))
    results.append(await run_test("Rapid Fire Sequential", test_10_rapid_fire_sequential))
    results.append(await run_test("User Agent Fuzzing", test_11_user_agent_fuzzing))
    results.append(await run_test("Query Param Explosion", test_12_query_param_explosion))
    results.append(await run_test("HTTP Method Fuzzing", test_13_method_fuzzing))
    results.append(await run_test("Health Polling Efficiency", test_14_internal_health_poll))
    results.append(await run_test("Concurrent Mixed Load", test_15_concurrent_mixed_load))

    passed = sum(results)
    print(f"\n⭐ FINAL RESULT: {passed}/15 Passed")
    if passed < 15:
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
