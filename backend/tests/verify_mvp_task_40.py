import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.v2.user import request_password_reset

async def verify_task_40():
    print("\n>>> STARTING VERIFICATION: MVP TASK 40 (PASSWORD RESET)")
    
    # 1. Test Reset Request
    print("  Testing password reset request...")
    
    # Mock Supabase
    with patch('core.auth.supabase_client.supabase.auth.reset_password_for_email', return_value={"data": {}, "error": None}) as mock_reset:
        
        email = "u40@ex.com"
        res = await request_password_reset(email=email)
        
        print(f"    Response Status: {res['status']}")
        print(f"    Response Message: {res['message']}")
        
        # Verify Supabase was called
        mock_reset.assert_called_once_with(email)
        
        assert res["status"] == "success"
        assert "reset link" in res["message"]
        print("    ✅ SUCCESS: Supabase reset flow triggered.")

    # 2. Test Error Handling (Anti-Enumeration)
    print("\n  Testing anti-enumeration (graceful error handling)...")
    with patch('core.auth.supabase_client.supabase.auth.reset_password_for_email', side_effect=Exception("Supabase Error")):
        res_err = await request_password_reset(email="nonexistent@ex.com")
        
        # Even if it fails, we should return success to hide email presence
        assert res_err["status"] == "success"
        print("    ✅ SUCCESS: Error hidden to prevent email enumeration.")

    print("\n✅ ALL MVP TASK 40 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_40())
