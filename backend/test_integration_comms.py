import asyncio
import httpx
import time
import json

BASE_URL = "http://127.0.0.1:8000"

async def test_integration():
    print("\n" + "="*100)
    print("🚀 ROUTEMASTER INTEGRATION & COMMUNICATION TEST")
    print("="*100)

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. CORS Preflight Test
        print("\n[1] CORS Preflight Check")
        res = await client.options(f"{BASE_URL}/api/v2/search/unified", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization"
        })
        print(f"   Status: {res.status_code}")
        print(f"   ACAO Header: {res.headers.get('Access-Control-Allow-Origin')}")
        print(f"   ACAM Header: {res.headers.get('Access-Control-Allow-Methods')}")
        
        # 2. Unified Search Integration
        print("\n[2] Unified Search Integration (NDLS -> KOTA)")
        try:
            res = await client.get(f"{BASE_URL}/api/v2/search/unified", params={
                "source": "NDLS",
                "destination": "KOTA",
                "date": "2026-03-15",
                "quota": "GN"
            }, headers={"X-Dev-Bypass": "TRUE"})
            print(f"   Status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                print(f"   Results Found: {len(data.get('results', []))}")
                print(f"   Session ID: {data.get('session_id')}")
            else:
                print(f"   Response Body: {res.text}")
        except Exception as e:
            print(f"   Error: {type(e).__name__}: {e}")

        # 3. Live Station Integration
        print("\n[3] Live Station Board (NDLS)")
        try:
            res = await client.get(f"{BASE_URL}/api/v2/live/station/NDLS", headers={"X-Dev-Bypass": "TRUE"})
            print(f"   Status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                print(f"   Trains Found: {len(data.get('trains', []))}")
            else:
                print(f"   Response Body: {res.text}")
        except Exception as e:
            print(f"   Error: {e}")

        # 4. SOS Emergency Trigger
        print("\n[4] SOS Emergency Trigger")
        try:
            sos_payload = {
                "lat": 28.6139,
                "lng": 77.2090,
                "name": "Integration Test User",
                "phone": "9999999999",
                "extra": "Integration Test SOS"
            }
            res = await client.post(f"{BASE_URL}/api/sos/", json=sos_payload, headers={"X-Dev-Bypass": "TRUE"})
            print(f"   Status: {res.status_code}")
            if res.status_code == 200 or res.status_code == 201:
                print(f"   Incident ID: {res.json().get('id')}")
            else:
                print(f"   Response Body: {res.text}")
        except Exception as e:
            print(f"   Error: {e}")

        # 5. Auth Bypass & RBAC Check (Admin Endpoint)
        print("\n[5] Auth Bypass & RBAC (Admin Endpoint)")
        try:
            res = await client.get(f"{BASE_URL}/api/v2/admin/system/health", headers={"X-Dev-Bypass": "TRUE"})
            print(f"   Status: {res.status_code}")
            if res.status_code == 200:
                print(f"   Admin Status (Uptime): {res.json().get('uptime_human')}")
            else:
                print(f"   Response Body: {res.text}")
        except Exception as e:
            print(f"   Error: {e}")

        # 6. GZip Compression Check
        print("\n[6] GZip Compression Check")
        res = await client.get(f"{BASE_URL}/health", headers={"Accept-Encoding": "gzip"})
        print(f"   Content-Encoding: {res.headers.get('Content-Encoding')}")

        # 7. Rate Limit Burst Check
        print("\n[7] Rate Limit Burst (10 reqs/sec from Local)")
        start = time.time()
        tasks = [client.get(f"{BASE_URL}/health") for _ in range(10)]
        results = await asyncio.gather(*tasks)
        dur = time.time() - start
        success = sum(1 for r in results if r.status_code == 200)
        print(f"   Successful: {success}/10 in {dur:.2f}s")
        print("   ANALYSIS: Localhost bypasses rate limit (Status 200).")

if __name__ == "__main__":
    asyncio.run(test_integration())
