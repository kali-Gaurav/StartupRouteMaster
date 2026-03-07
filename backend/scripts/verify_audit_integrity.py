import sys
import os
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database.session import SessionLocal
from database.models import Booking, AuditLog, EscrowStatus

def verify_atomic_audit():
    print("🔍 Testing Atomic Audit Integrity...")
    db = SessionLocal()
    try:
        # 1. Pick a booking
        booking = db.query(Booking).first()
        if not booking:
            print("❌ No bookings found to test.")
            return

        # 2. Update status using hardened method
        print(f"  Attempting state transition for Booking {booking.id}...")
        try:
            booking.update_escrow_status(
                db, 
                EscrowStatus.FAILED, 
                message="Integrity Verification Test",
                performed_by="TEST_RUNNER"
            )
            db.commit()
            print("  ✅ Database commit successful.")
        except Exception as e:
            print(f"  ❌ Transition failed: {e}")
            db.rollback()
            return

        # 3. Verify Log exists
        log = db.query(AuditLog).filter(
            AuditLog.entity_id == str(booking.id),
            AuditLog.performed_by == "TEST_RUNNER"
        ).first()
        
        if log:
            print(f"  ✅ Audit Log FOUND: {log.action} | {log.old_value} -> {log.new_value}")
        else:
            print("  ❌ Audit Log MISSING!")

    finally:
        db.close()

if __name__ == "__main__":
    verify_atomic_audit()
