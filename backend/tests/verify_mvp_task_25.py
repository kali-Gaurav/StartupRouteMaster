import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus
from services.platform_config_service import PlatformConfigService
from api.v2.booking import initiate_service
from unittest.mock import MagicMock

async def verify_task_25():
    print("\n>>> STARTING VERIFICATION: MVP TASK 25 (DYNAMIC FEE ADJUSTER)")
    
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    user_id = "u25"
    journey_id = "J25_FEE_TEST"
    
    # 0. Setup
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    u = User(id=user_id, email="u25@ex.com")
    db.add(u)
    db.commit()
    
    # 1. Test Default Fee (Should be 49.0)
    print("  Testing default UNLOCK_FEE...")
    db.execute(text("DELETE FROM platform_configs WHERE key = 'UNLOCK_FEE'"))
    db.commit()
    
    fee_default = PlatformConfigService.get_fee(db, "UNLOCK_FEE")
    print(f"    Default Fee: ₹{fee_default}")
    assert fee_default == 49.0

    # 2. Update Fee to ₹99
    print("\n  Updating UNLOCK_FEE to ₹99.0 via service...")
    PlatformConfigService.set_config(db, "UNLOCK_FEE", "99.0", "Testing dynamic adjuster")
    
    fee_updated = PlatformConfigService.get_fee(db, "UNLOCK_FEE")
    print(f"    Updated Fee: ₹{fee_updated}")
    assert fee_updated == 99.0

    # 3. Verify Integration in initiate_service
    print("\n  Verifying initiate_service uses updated fee...")
    
    # Mock journey cache
    with patch('services.journey_cache.get_journey', return_value={"total_fare": 0.0}):
        with patch('services.merchant_vpa_service.merchant_vpa_service.get_next_vpa', return_value={"vpa": "test@upi", "name": "Test"}):
            # We need to mock get_current_user or pass mock user
            res = await initiate_service(journey_id=journey_id, service_type="UNLOCK", user=u, db=db)
            
            print(f"    Booking Amount: ₹{res['amount']}")
            # It will be 99.0 + some random paisa (e.g. 99.42)
            assert 99.0 < res['amount'] < 100.0
            print("    SUCCESS: initiate_service applied the dynamic fee.")

    # 4. Cleanup
    db.query(Booking).filter(Booking.id == res['id']).delete()
    db.delete(u)
    db.execute(text("DELETE FROM platform_configs WHERE key = 'UNLOCK_FEE'"))
    db.commit()
    
    print("\n✅ ALL MVP TASK 25 SUBTASKS VERIFIED!")

from unittest.mock import patch
if __name__ == "__main__":
    asyncio.run(verify_task_25())
