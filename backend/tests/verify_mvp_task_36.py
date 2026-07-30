import asyncio
import sys
import os
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.dependencies import require_role
from database.models import User

async def verify_task_36():
    print("\n>>> STARTING VERIFICATION: MVP TASK 36 (RBAC AUDIT)")
    
    # 1. Test Unauthorized Access (Role: user)
    print("  Testing access for 'user' to agent-restricted role...")
    mock_user = MagicMock(spec=User)
    mock_user.role = "user"
    mock_user.id = "u36_fake"
    
    checker = require_role(["agent", "admin"])
    
    try:
        checker(mock_user)
        print("    ❌ FAILURE: Regular user bypassed RBAC!")
        assert False
    except HTTPException as e:
        print(f"    ✅ SUCCESS: Caught expected block: {e.status_code} - {e.detail}")
        assert e.status_code == 403

    # 2. Test Authorized Access (Role: agent)
    print("\n  Testing access for 'agent'...")
    mock_agent = MagicMock(spec=User)
    mock_agent.role = "agent"
    
    try:
        res = checker(mock_agent)
        print(f"    ✅ SUCCESS: Agent allowed access.")
        assert res == mock_agent
    except HTTPException as e:
        print(f"    ❌ FAILURE: Authorized agent blocked! {e.detail}")
        assert False

    # 3. Test Authorized Access (Role: admin)
    print("\n  Testing access for 'admin'...")
    mock_admin = MagicMock(spec=User)
    mock_admin.role = "admin"
    
    try:
        res = checker(mock_admin)
        print(f"    ✅ SUCCESS: Admin allowed access.")
        assert res == mock_admin
    except HTTPException as e:
        print(f"    ❌ FAILURE: Authorized admin blocked! {e.detail}")
        assert False

    print("\n✅ ALL MVP TASK 36 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_36())
