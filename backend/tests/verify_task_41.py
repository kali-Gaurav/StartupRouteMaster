import sys
import os
from datetime import datetime
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.unlock_service import UnlockService
from database.session import SessionLocal
from database.models import User, Booking, PaymentSession, AuditLog

def verify_task_41():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 41 (UNLOCK SERVICE)")
    
    db = SessionLocal()
    user_id = "test-user-41"
    route_id = "T12625_20260308"
    
    # 0. Create Test User
    test_user = User(id=user_id, email="test41@example.com", full_name="Test User 41")
    db.merge(test_user) # Use merge to handle existing
    db.commit()
    
    # 1. Test Masking Logic
    print("  Testing Masking Logic...")
    route_data = {
        "journey_id": route_id,
        "segments": [{
            "train_number": "12625",
            "train_name": "Kerala Express",
            "departure_platform": "4"
        }]
    }
    masked = UnlockService.mask_route(route_data)
    print(f"    Masked Train: {masked['segments'][0]['train_number']}")
    assert masked['segments'][0]['train_number'] == "XXXXX"
    assert masked['is_locked'] == True
    
    # 2. Test Unlock Request Creation
    print("\n  Testing Unlock Request Creation...")
    booking = UnlockService.create_unlock_request(db, user_id, route_id)
    
    print(f"    Booking ID: {booking.id}")
    print(f"    Service Type: {booking.service_type}")
    assert booking.service_type == "UNLOCK"
    assert booking.is_unlocked == False
    
    # Verify PaymentSession was created
    pay_session = db.query(PaymentSession).filter(PaymentSession.user_id == user_id).first()
    print(f"    Payment Session Code: {pay_session.session_code}")
    assert pay_session is not None
    
    # 3. Test Fulfillment
    print("\n  Testing Unlock Fulfillment...")
    success = UnlockService.fulfill_unlock(db, booking.id)
    assert success == True
    
    # Refresh and check
    db.refresh(booking)
    print(f"    Unlocked Status: {booking.is_unlocked}")
    assert booking.is_unlocked == True
    assert booking.escrow_status.value == "COMPLETED"
    
    # 4. Check Audit Log
    print("\n  Checking Audit Logs...")
    logs = db.query(AuditLog).filter(AuditLog.entity_id == booking.id).all()
    print(f"    Audit Log Count: {len(logs)}")
    assert len(logs) >= 2 # Initiated and Completed
    
    # CLEANUP (Optional for local dev, but good practice)
    db.delete(pay_session)
    db.delete(booking)
    for l in logs: db.delete(l)
    db.commit()
    
    print("\n✅ TASK 41 FULLY VERIFIED: Monetization flow is functional.")

if __name__ == "__main__":
    verify_task_41()
