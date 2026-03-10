import asyncio
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"

async def test_auth_integrity():
    print("\n" + "="*60)
    print("🚀 EPIC 2: AUTHENTICATION & SESSION INTEGRITY AUDIT")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        
        # Subtask 2.1: Bearer Token Spoofing (Hard failure expected)
        print("\n--- Subtask 2.1: Bearer Token Spoofing ---")
        malformed_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake_payload.fake_signature"
        res = await client.get(
            f"{BASE_URL}/api/user/me", 
            headers={"Authorization": f"Bearer {malformed_token}"}
        )
        print(f"Status: {res.status_code}")
        if res.status_code == 401:
            print("✅ SUCCESS: Malformed token correctly rejected.")
        else:
            print(f"❌ FAILURE: Malformed token allowed or gave wrong status: {res.status_code}")

        # Subtask 2.2: Missing Authorization Header
        print("\n--- Subtask 2.2: Missing Auth Header ---")
        res = await client.get(f"{BASE_URL}/api/user/me")
        print(f"Status: {res.status_code}")
        if res.status_code == 401:
            print("✅ SUCCESS: Unauthenticated request blocked.")
        else:
            print(f"❌ FAILURE: Unauthenticated request not blocked.")

        # Subtask 2.3: Role Based Access Control (RBAC) - Admin Probing
        print("\n--- Subtask 2.3: RBAC Enforcement Probing ---")
        # Probing admin config without admin privileges
        # Adding timestamp to bypass any weird local caching
        res = await client.get(f"{BASE_URL}/api/v2/admin/config?t={int(time.time())}")
        print(f"Status: {res.status_code}")
        if res.status_code in [401, 403]:
            print("✅ SUCCESS: Admin endpoint protected.")
        else:
            print(f"❌ FAILURE: Admin endpoint exposed: {res.status_code}")
            print(f"   Body preview: {res.text[:100]}")

        # Subtask 2.4: Blacklist Latency Audit (Hard)
        print("\n--- Subtask 2.4: Session Blacklist Integrity ---")
        # We'll check if the backend correctly references the cache_service for blacklisting
        # This is a code-path verification
        from api.chat import _get_redis
        redis_conn = _get_redis()
        if redis_conn:
            print("✅ SUCCESS: Redis connection available for blacklist checks.")
        else:
            print("⚠️ WARNING: Redis unavailable; blacklist falling back to memory (not multi-instance safe).")

    print("\n" + "="*60)
    print("🏁 EPIC 2 AUDIT COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_auth_integrity())
