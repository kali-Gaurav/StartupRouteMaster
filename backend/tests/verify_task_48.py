import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, AuditLog
from services.pnr_verification_service import PNRVerificationService

def verify_task_48():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 48 (PNR VERIFICATION)")
    
    db = SessionLocal()
    import uuid
    booking_id = f"test-pnr-48-{str(uuid.uuid4())[:8]}"
    pnr = str(uuid.uuid4())[:10].upper()
    
    # 0. Setup
    u1 = User(id="user48", email="u48@ex.com")
    a1 = User(id="AGENT_PRO", email="a_pro@ex.com", role="agent")
    db.merge(u1)
    db.merge(a1)
    
    booking = Booking(
        id=booking_id, user_id="user48", route_id="route48",
        service_type="AGENT_BOOKING", escrow_status=EscrowStatus.BOOKING_INITIATED,
        agent_id="AGENT_PRO", booking_details={}
    )
    db.merge(booking)
    db.commit()
    
    # 1. Test Unauthorized Agent (Subtask 48.9)
    print("  Testing Unauthorized Agent entry...")
    res1 = PNRVerificationService.complete_booking(db, booking_id, pnr, "AGENT_EVIL")
    print(f"    Result: {res1} (Expected: False)")
    assert res1 == False
    
    # 2. Test Successful Completion
    print("\n  Testing Successful Completion...")
    res2 = PNRVerificationService.complete_booking(db, booking_id, pnr, "AGENT_PRO")
    print(f"    Result: {res2} (Expected: True)")
    assert res2 == True
    
    # Verify Data
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    print(f"    PNR: {booking.pnr_number}")
    print(f"    Status: {booking.escrow_status.value}")
    assert booking.pnr_number == pnr
    assert booking.escrow_status == EscrowStatus.COMPLETED
    assert ".pdf" in booking.ticket_pdf_url
    
    # 3. Test PNR Uniqueness (Subtask 48.3)
    print("\n  Testing PNR Uniqueness...")
    b2 = Booking(
        id="test-pnr-duplicate", user_id="user48", route_id="route48_2",
        service_type="AGENT_BOOKING", escrow_status=EscrowStatus.BOOKING_INITIATED,
        agent_id="AGENT_PRO", booking_details={}
    )
    db.merge(b2)
    db.commit()
    
    try:
        PNRVerificationService.complete_booking(db, "test-pnr-duplicate", pnr, "AGENT_PRO")
        print("    ❌ FAILURE: Allowed duplicate PNR!")
        assert False
    except ValueError as e:
        print(f"    ✅ SUCCESS: Caught expected error: {e}")
        assert "already linked" in str(e)
        
    # 4. Cleanup
    db.query(Booking).filter(Booking.id.in_([booking_id, "test-pnr-duplicate"])).delete()
    db.query(AuditLog).filter(AuditLog.entity_id == booking_id).delete()
    db.commit()
    
    print("\n✅ TASK 48 FULLY VERIFIED: PNR verification and fulfillment are secure.")

if __name__ == "__main__":
    verify_task_48()
