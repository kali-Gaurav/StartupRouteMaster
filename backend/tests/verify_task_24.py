import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus
from services.payment_vpa_service import PaymentVPAService

def verify_task_24():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 24 (SPLIT PAYMENTS)")
    
    db = SessionLocal()
    booking_id = "B24_SPLIT_TEST"
    
    # 0. Setup test data
    u = User(id="u24", email="u24@ex.com")
    db.merge(u)
    
    # Required Total: ₹100
    b1 = Booking(
        id=booking_id, user_id="u24", 
        amount_paid=100.0, 
        escrow_status=EscrowStatus.CREATED,
        transaction_history=[],
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    # 1. First Transaction (Partial)
    print("  Adding partial transaction: ₹40...")
    PaymentVPAService.add_transaction(db, booking_id, "UTR24_1", 40.0)
    
    b1 = db.query(Booking).filter(Booking.id == booking_id).first()
    print(f"    Current Status: {b1.escrow_status.value}")
    print(f"    History Length: {len(b1.transaction_history)}")
    
    assert b1.escrow_status == EscrowStatus.CREATED
    assert len(b1.transaction_history) == 1
    
    # 2. Second Transaction (Completes the total)
    print("\n  Adding completing transaction: ₹60...")
    PaymentVPAService.add_transaction(db, booking_id, "UTR24_2", 60.0)
    
    b1 = db.query(Booking).filter(Booking.id == booking_id).first()
    print(f"    Current Status: {b1.escrow_status.value}")
    print(f"    History Length: {len(b1.transaction_history)}")
    
    # Sum is 100, should be VERIFIED
    assert b1.escrow_status == EscrowStatus.VERIFIED
    assert len(b1.transaction_history) == 2
    
    # 3. Cleanup
    db.delete(b1)
    db.commit()
    
    print("\n✅ TASK 24 FULLY VERIFIED: Multiple transactions are aggregated correctly for verification.")

if __name__ == "__main__":
    verify_task_24()
