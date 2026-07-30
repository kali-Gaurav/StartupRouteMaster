import asyncio
import sys
import os
from datetime import datetime, date, timedelta
from database.session import SessionLocal
from database.models import User, Booking, CommissionTracking, EscrowStatus
from api.v2.admin import get_finance_breakdown

async def verify_task_20():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 20 (FINANCE BREAKDOWN API)")
    
    db = SessionLocal()
    # USE FIXED DATE matching previous tests (March 7)
    test_date = date(2026, 3, 7)
    start_dt = datetime.combine(test_date, datetime.min.time())
    
    # 0. Setup test data
    u = User(id="u20", email="u20@ex.com")
    db.merge(u)
    
    # 1 Unlock (₹49)
    b1 = Booking(id="B20_1", user_id="u20", amount_paid=49.0, service_type="UNLOCK", escrow_status=EscrowStatus.COMPLETED, booking_details={}, created_at=start_dt)
    # 1 Agent Booking (₹1010 total, where ₹10 is fee)
    b2 = Booking(id="B20_2", user_id="u20", amount_paid=1010.0, service_type="AGENT_BOOKING", escrow_status=EscrowStatus.VERIFIED, booking_details={}, created_at=start_dt)
    # 1 Commission (₹10)
    c1 = CommissionTracking(id="C20_1", user_id="u20", booking_id="B20_2", amount=10.0, created_at=start_dt)
    
    db.merge(b1); db.merge(b2); db.merge(c1)
    db.commit()
    
    # 1. Fetch Breakdown
    print(f"  Fetching finance breakdown for {test_date}...")
    res = await get_finance_breakdown(start_date=test_date, end_date=test_date, db=db)
    
    print(f"    Total Revenue: ₹{res['total_revenue']}")
    print(f"    Total Commissions: ₹{res['total_commissions']}")
    print(f"    Net Profit: ₹{res['net_profit']}")
    
    # Revenue = 49 + 1010 = 1059
    # Commissions = 10
    # Profit = 1049
    
    assert res["total_revenue"] == 1059.0
    assert res["total_commissions"] == 10.0
    assert res["net_profit"] == 1049.0
    
    # 2. Cleanup
    db.query(CommissionTracking).filter(CommissionTracking.id == "C20_1").delete()
    db.query(Booking).filter(Booking.id.in_(["B20_1", "B20_2"])).delete()
    db.commit()
    
    print("\n✅ TASK 20 FULLY VERIFIED: Financial breakdown API provides accurate profit/loss visibility.")

if __name__ == "__main__":
    asyncio.run(verify_task_20())
