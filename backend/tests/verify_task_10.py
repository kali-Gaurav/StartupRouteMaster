import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus
import sqlalchemy

def verify_task_10():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 10 (DUPLICATE UTR PREVENTION)")
    
    db = SessionLocal()
    utr = "999988887777"
    
    # 0. Setup
    u = User(id="u10", email="u10@ex.com")
    db.merge(u)
    
    b1 = Booking(id="B10_1", user_id="u10", utr_number=utr, booking_details={})
    b2 = Booking(id="B10_2", user_id="u10", utr_number=utr, booking_details={})
    
    # 1. Test Uniqueness at DB Level
    print("  Attempting to save first booking with UTR...")
    db.merge(b1)
    db.commit()
    print("    Success.")
    
    print("\n  Attempting to save second booking with IDENTICAL UTR...")
    try:
        db.add(b2)
        db.commit()
        print("    ❌ FAILURE: DB allowed duplicate UTR!")
        assert False
    except sqlalchemy.exc.IntegrityError:
        db.rollback()
        print("    ✅ SUCCESS: DB blocked duplicate UTR (IntegrityError).")
        
    # 2. Cleanup
    db.query(Booking).filter(Booking.id.in_(["B10_1", "B10_2"])).delete()
    db.commit()
    
    print("\n✅ TASK 10 FULLY VERIFIED: UTR uniqueness is enforced at the database layer.")

if __name__ == "__main__":
    verify_task_10()
