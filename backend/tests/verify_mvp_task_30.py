import asyncio
import sys
import os
import hmac
import hashlib
import json
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.security import signature_guard, WEBHOOK_SECRET

async def verify_task_30():
    print("\n>>> STARTING VERIFICATION: MVP TASK 30 (WEBHOOK SIGNATURES)")
    
    # 1. Test Valid Signature
    print("  Testing valid signature...")
    payload = {"utr_number": "123456789012", "amount": 49.0}
    body_bytes = json.dumps(payload, separators=(',', ':')).encode()
    
    valid_sig = hmac.new(
        WEBHOOK_SECRET.encode(),
        body_bytes,
        hashlib.sha256
    ).hexdigest()
    
    req_valid = MagicMock()
    req_valid.headers = {"X-RM-Signature": valid_sig}
    req_valid.body = AsyncMock(return_value=body_bytes)
    
    try:
        res = await signature_guard(req_valid)
        print(f"    ✅ SUCCESS: Valid signature accepted.")
        assert res is True
    except HTTPException as e:
        print(f"    ❌ FAILURE: Valid signature rejected! {e.detail}")
        assert False

    # 2. Test Invalid Signature
    print("\n  Testing invalid signature...")
    req_invalid = MagicMock()
    req_invalid.headers = {"X-RM-Signature": "wrong_hash"}
    req_invalid.body = AsyncMock(return_value=body_bytes)
    
    try:
        await signature_guard(req_invalid)
        print("    ❌ FAILURE: Invalid signature allowed!")
        assert False
    except HTTPException as e:
        print(f"    ✅ SUCCESS: Caught expected error: {e.status_code} - {e.detail}")
        assert e.status_code == 401

    print("\n✅ ALL MVP TASK 30 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_30())
