import sys
import os
from datetime import datetime, date
from database.session import SessionLocal
from database.models import User, Booking, CommissionTracking, DailyReconciliation, EscrowStatus
from services.reconciliation_service import ReconciliationService

def verify_task_49():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 49 (RECONCILIATION ENGINE)")
    
    db = SessionLocal()
    # USE FIXED DATE matching the debug log discovery (March 7)
    today = date(2026, 3, 7)
    
    # 0. Setup dummy data for today
    print(f"  Setting up test transactions for {today}...")
    u1 = User(id="u49", email="u49@ex.com")
    db.merge(u1)
    
    now = datetime.utcnow()
    
    # 2 Unlocks (₹49 each)
    b1 = Booking(id="B49_1", user_id="u49", amount_paid=49.0, service_type="UNLOCK", escrow_status=EscrowStatus.COMPLETED, booking_details={}, created_at=now)
    b2 = Booking(id="B49_2", user_id="u49", amount_paid=49.0, service_type="UNLOCK", escrow_status=EscrowStatus.COMPLETED, booking_details={}, created_at=now)
    
    # 1 Agent Booking (₹510 total, where ₹10 is fee)
    b3 = Booking(id="B49_3", user_id="u49", amount_paid=510.0, service_type="AGENT_BOOKING", escrow_status=EscrowStatus.VERIFIED, booking_details={}, created_at=now)
    
    # 1 Commission (₹10)
    c1 = CommissionTracking(id="C49_1", user_id="u49", booking_id="B49_3", amount=10.0, created_at=now)
    
    db.merge(b1); db.merge(b2); db.merge(b3); db.merge(c1)
    db.commit()
    
    # 1. Run Recon
    print("  Running Daily Reconciliation...")
    recon = ReconciliationService.run_daily_recon(db, today)
    
    print(f"    Date: {recon.recon_date}")
    print(f"    Total Revenue: ₹{recon.total_revenue}")
    print(f"    Total Unlock Fees: ₹{recon.total_unlocked_fees}")
    print(f"    Total Agent Commissions: ₹{recon.total_agent_commissions}")
    
    # Expected: 
    # Rev = 49 + 49 + 510 = 608
    # Unlock = 49 + 49 = 98
    # Comm = 10
    
    assert recon.total_revenue == 608.0
    assert recon.total_unlocked_fees == 98.0
    assert recon.total_agent_commissions == 10.0
    
    # 2. Cleanup
    db.query(DailyReconciliation).filter(DailyReconciliation.recon_date == today).delete()
    db.query(CommissionTracking).filter(CommissionTracking.id == "C49_1").delete()
    db.query(Booking).filter(Booking.id.in_(["B49_1", "B49_2", "B49_3"])).delete()
    db.commit()
    
    print("\n✅ TASK 49 FULLY VERIFIED: Reconciliation logic accurately balances daily revenue.")

if __name__ == "__main__":
    verify_task_49()
