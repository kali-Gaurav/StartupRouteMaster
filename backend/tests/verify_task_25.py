import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, MerchantVPA
from api.v2.admin import verify_payment

async def verify_task_25():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 25 (DAILY LIMIT TRACKING)")
    
    db = SessionLocal()
    vpa = "anthonynagar1122-1@oksbi"
    
    # 0. Get initial volume
    m = db.query(MerchantVPA).filter(MerchantVPA.vpa == vpa).first()
    initial_vol = m.current_daily_volume
    print(f"  Initial Volume for {vpa}: ₹{initial_vol}")
    
    # 1. Create a booking linked to this VPA
    u = User(id="u25", email="u25@ex.com")
    db.merge(u)
    
    booking_id = "B25_LIMIT_TEST"
    b1 = Booking(
        id=booking_id, user_id="u25", 
        service_type="UNLOCK",
        escrow_status=EscrowStatus.UTR_SUBMITTED,
        merchant_vpa=vpa,
        amount_paid=49.0,
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    # 2. Verify Payment (Should trigger increment)
    print("  Verifying payment of ₹49...")
    await verify_payment(booking_id, db)
    
    # 3. Check final volume
    db.refresh(m)
    final_vol = m.current_daily_volume
    print(f"  Final Volume for {vpa}: ₹{final_vol}")
    
    assert final_vol == initial_vol + 49.0
    print("    Increment Check: OK")
    
    # 4. Cleanup
    db.query(Booking).filter(Booking.id == booking_id).delete()
    db.commit()
    
    print("\n✅ TASK 25 FULLY VERIFIED: Merchant daily volumes are tracked in real-time.")

if __name__ == "__main__":
    asyncio.run(verify_task_25())
