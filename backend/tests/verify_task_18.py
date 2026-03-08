import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import MerchantVPA
from api.v2.admin import toggle_vpa_status, bulk_activate_vpas
from fastapi import HTTPException

async def verify_task_18():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 18 (VPA STATUS CONTROL)")
    
    db = SessionLocal()
    vpa1 = "anthonynagar1122-1@oksbi"
    vpa2 = "8529841981@ptsbi"
    
    # 0. Ensure both active
    await bulk_activate_vpas(db)
    print("  Ensured all VPAs are active.")
    
    # 1. Test Single Toggle
    print("  Toggling VPA 1 off...")
    res = await toggle_vpa_status(vpa1, db)
    assert res["is_active"] == False
    
    # 2. Test Safety Lock (Subtask 18.3)
    print("  Attempting to toggle VPA 2 off (Last Active)...")
    try:
        await toggle_vpa_status(vpa2, db)
        print("    ❌ FAILURE: Allowed deactivating last VPA!")
        assert False
    except HTTPException as e:
        print(f"    ✅ SUCCESS: Blocked last VPA deactivation: {e.detail}")
        assert e.status_code == 400
        
    # 3. Test Bulk Activate
    print("  Bulk activating all...")
    await bulk_activate_vpas(db)
    m1 = db.query(MerchantVPA).filter(MerchantVPA.vpa == vpa1).first()
    assert m1.is_active == True
    print("    Success: All VPAs active again.")
    
    print("\n✅ TASK 18 FULLY VERIFIED: VPA status control and safety locks are functional.")

if __name__ == "__main__":
    asyncio.run(verify_task_18())
