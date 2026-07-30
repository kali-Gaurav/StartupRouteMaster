import asyncio
import sys
import os
from unittest.mock import MagicMock
from fastapi import HTTPException

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.v2.admin_auth import admin_login, AdminLoginRequest
from services.cache_service import cache_service

async def verify_task_32():
    print("\n>>> STARTING VERIFICATION: MVP TASK 32 (BRUTE FORCE PROTECTION)")
    
    # Reset cache for test IP
    test_ip = "1.2.3.4"
    if cache_service.is_available():
        cache_service.redis.delete(f"login_fails:{test_ip}")
    
    payload = AdminLoginRequest(username="wrong_admin", password="wrong_password")
    mock_request = MagicMock()
    mock_request.client.host = test_ip
    
    # 1. Simulate 10 Failures
    print("  Simulating 10 failed login attempts...")
    for i in range(10):
        try:
            await admin_login(payload, mock_request)
        except HTTPException as e:
            assert e.status_code == 401
            
    # 2. 11th attempt should be blocked
    print("  Verifying 11th attempt is BLOCKED (429)...")
    try:
        await admin_login(payload, mock_request)
        print("    ❌ FAILURE: 11th attempt allowed!")
        assert False
    except HTTPException as e:
        print(f"    ✅ SUCCESS: Caught expected block: {e.status_code} - {e.detail}")
        assert e.status_code == 429

    print("\n✅ ALL MVP TASK 32 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_32())
