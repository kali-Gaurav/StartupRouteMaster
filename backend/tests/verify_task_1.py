import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import SessionLocal
from database.models import MerchantVPA, AuditLog
from services.payment_vpa_service import PaymentVPAService

def verify_task_1():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 1 (VPA ROTATION)")
    
    db = SessionLocal()
    
    # 1. Reset all to zero
    PaymentVPAService.reset_daily_volumes(db)
    print("  Volumes reset to zero.")
    
    # 2. Simulate Assignments
    assignments = []
    for i in range(10):
        vpa = PaymentVPAService.get_next_vpa(db)
        assignments.append(vpa)
        # Simulate booking volume
        PaymentVPAService.increment_volume(db, vpa, 100.0)
        
    print(f"  Simulated 10 assignments: {assignments}")
    
    # 3. Verify Alternation
    # Since we increment volume each time, they should strictly alternate if limits are same
    vpa1 = "anthonynagar1122-1@oksbi"
    vpa2 = "8529841981@ptsbi"
    
    vpa1_count = assignments.count(vpa1)
    vpa2_count = assignments.count(vpa2)
    
    print(f"  VPA 1 Usage: {vpa1_count}")
    print(f"  VPA 2 Usage: {vpa2_count}")
    
    assert vpa1_count == 5
    assert vpa2_count == 5
    
    # 4. Test Inactivity Filter
    print("\n  Testing Inactivity Filter...")
    # Deactivate VPA 1
    m1 = db.query(MerchantVPA).filter(MerchantVPA.vpa == vpa1).first()
    m1.is_active = False
    db.commit()
    
    vpa_after_deactivation = PaymentVPAService.get_next_vpa(db)
    print(f"  Next VPA after deactivating VPA 1: {vpa_after_deactivation}")
    assert vpa_after_deactivation == vpa2
    
    # 5. Cleanup
    m1.is_active = True
    PaymentVPAService.reset_daily_volumes(db)
    db.commit()
    
    print("\n✅ TASK 1 FULLY VERIFIED: Merchant rotation is perfectly balanced.")

if __name__ == "__main__":
    verify_task_1()
