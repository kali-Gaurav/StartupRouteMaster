import asyncio
import sys
import os
from unittest.mock import MagicMock
from fastapi import HTTPException

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.v2.webhooks import verify_ip

async def verify_task_28():
    print("\n>>> STARTING VERIFICATION: MVP TASK 28 (IP WHITELISTING)")
    
    # 1. Test Unauthorized IP
    print("  Testing unauthorized IP (8.8.8.8)...")
    req_fake = MagicMock()
    req_fake.headers = {}
    req_fake.client.host = "8.8.8.8"
    
    try:
        verify_ip(req_fake)
        print("    ❌ FAILURE: Unauthorized IP allowed!")
        assert False
    except HTTPException as e:
        print(f"    ✅ SUCCESS: Caught expected error: {e.status_code} - {e.detail}")
        assert e.status_code == 403

    # 2. Test Authorized IP (Localhost)
    print("\n  Testing authorized IP (127.0.0.1)...")
    req_safe = MagicMock()
    req_safe.headers = {}
    req_safe.client.host = "127.0.0.1"
    
    try:
        res = verify_ip(req_safe)
        print(f"    ✅ SUCCESS: IP {res} allowed.")
        assert res == "127.0.0.1"
    except HTTPException as e:
        print(f"    ❌ FAILURE: Authorized IP blocked! {e.detail}")
        assert False

    print("\n✅ ALL MVP TASK 28 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_28())
