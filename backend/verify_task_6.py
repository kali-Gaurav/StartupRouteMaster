import sys
import os
import uuid

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionLocal
from database.models import User, Booking
from services.refund_service import RefundService

def create_mock_data(db):
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test_refund_{user_id}@example.com",
        role="user"
    )
    db.add(user)
    db.commit()

    booking1 = Booking(id=str(uuid.uuid4()), user_id=user_id, amount_paid=1000.0, booking_status="pending", booking_details={})
    booking2 = Booking(id=str(uuid.uuid4()), user_id=user_id, amount_paid=6000.0, booking_status="pending", booking_details={})
    booking3 = Booking(id=str(uuid.uuid4()), user_id=user_id, amount_paid=1000.0, booking_status="pending", booking_details={}) # For partial
    booking_no_vpa = Booking(id=str(uuid.uuid4()), user_id=user_id, amount_paid=1000.0, booking_status="pending", booking_details={})
    
    db.add_all([booking1, booking2, booking3, booking_no_vpa])
    db.commit()

    return user_id, booking1.id, booking2.id, booking3.id, booking_no_vpa.id

def verify_task_6():
    print("=== Verifying Task 6: Refund Queue State Machine ===")
    
    db = SessionLocal()
    service = RefundService(db)
    
    try:
        u_id, b1_id, b2_id, b3_id, b_novpa_id = create_mock_data(db)
        
        # 1. Test Auto-trigger & State Machine (Task 6.1, 6.2)
        print("Testing Auto-trigger on IRCTC_SOLD_OUT...")
        res1 = service.create_refund_request(b1_id, "IRCTC_SOLD_OUT", 1000.0)
        assert res1["success"] is True
        assert res1["refund_status"] == "REFUND_PENDING"
        
        booking1 = db.query(Booking).filter(Booking.id == b1_id).first()
        assert booking1.booking_status == "cancelled" # Auto-cancelled
        print("[OK] Auto-trigger and PENDING state works")
        
        # Process the refund
        proc1 = service.process_refund(b1_id, target_vpa="user@upi")
        assert proc1["success"] is True
        assert "receipt_id" in proc1["receipt"] # Task 6.6: Receipt Generation
        print("[OK] State transitioned to SUCCESS with Receipt")

        # 2. Test High-Value Manual Approval (Task 6.4)
        print("Testing High-Value Manual Approval...")
        res2 = service.create_refund_request(b2_id, "USER_CANCELLED", 6000.0)
        assert res2["refund_status"] == "REQUIRES_APPROVAL"
        
        proc2 = service.process_refund(b2_id)
        assert proc2["success"] is False # Should be blocked
        
        # Approve it
        appr_res = service.admin_approve_refund(b2_id)
        assert appr_res["success"] is True
        print("[OK] High-value refund correctly blocked and approved")

        # 3. Test Partial Refund Logic (Task 6.5)
        print("Testing Partial Refund Logic...")
        res3 = service.create_refund_request(b3_id, "USER_CANCELLED", 1000.0, is_partial=True, cancellation_charge=150.0)
        assert res3["amount"] == 850.0
        print("[OK] Cancellation charges correctly subtracted")

        # 4. Test Missing VPA Auto-Retry/Fail (Task 6.3, 6.10)
        print("Testing VPA Verification Failure...")
        service.create_refund_request(b_novpa_id, "TEST", 1000.0)
        proc3 = service.process_refund(b_novpa_id) # Won't pass VPA because we cleared preferences
        assert proc3["success"] is False
        
        b_novpa = db.query(Booking).filter(Booking.id == b_novpa_id).first()
        assert b_novpa.booking_details["refund_info"]["status"] == "REFUND_FAILED"
        assert b_novpa.booking_details["refund_info"]["retry_count"] == 1
        print("[OK] Refund failed cleanly due to missing VPA, retry counter incremented")

        # 5. Bulk Processing (Task 6.7)
        print("Testing Bulk Processing...")
        bulk_res = service.process_bulk_refunds()
        assert bulk_res["success"] is True
        print(f"[OK] Bulk processing completed (Processed: {bulk_res['processed']}, Failed: {bulk_res['failed']})")

    finally:
        db.close()

    print("=== Task 6 Verification Complete ===")

if __name__ == "__main__":
    verify_task_6()
