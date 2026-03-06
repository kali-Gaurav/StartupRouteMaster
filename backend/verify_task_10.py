import sys
import os
import uuid
import httpx
import asyncio
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionLocal
from database.models import PaymentSession, User

def setup_expired_session():
    db = SessionLocal()
    try:
        user_id = str(uuid.uuid4())
        user = User(id=user_id, email=f"test10_{user_id}@example.com", role="user")
        db.add(user)
        db.commit()
        
        session_code = str(uuid.uuid4().hex[:6]).upper()
        
        # Create a session that is already expired (simulating a missed 10-min window)
        session = PaymentSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_code=session_code,
            amount=39.0,
            status="EXPIRED",
            expires_at=datetime.utcnow() # Expired right now
        )
        db.add(session)
        db.commit()
        
        return session_code
    finally:
        db.close()

async def verify_task_10():
    print("=== Verifying Task 10: QR Code Expiry & Refresh ===")
    
    expired_code = setup_expired_session()
    
    async with httpx.AsyncClient() as client:
        # 1. Test Refresh Session
        print(f"Testing Session Refresh for expired code {expired_code}...")
        
        # We need a fake JWT or to bypass auth for the test. 
        # Since the endpoint requires Depends(get_current_user), we should mock it or 
        # modify our test to use a direct service call if the endpoint rejects us.
        # Let's hit the endpoint and see if our auth mock from earlier works, 
        # if not, we'll verify the service directly.
        
        db = SessionLocal()
        from api.payments import refresh_payment_session
        from database.models import User
        
        old_session = db.query(PaymentSession).filter(PaymentSession.session_code == expired_code).first()
        test_user = db.query(User).filter(User.id == old_session.user_id).first()
        
        # Directly call the async endpoint function to bypass the FastAPI request lifecycle/auth middleware
        # for testing purposes.
        res = await refresh_payment_session(
            old_session_code=expired_code,
            db=db,
            current_user=test_user
        )
        
        assert res["success"] is True
        new_code = res["session_code"]
        assert new_code != expired_code
        assert len(new_code) == 6
        assert "upi://pay" in res["upi_link"]
        print(f"[OK] Session successfully refreshed. New code: {new_code}")
        
        # Verify old session is explicitly EXPIRED and new is PENDING
        old_check = db.query(PaymentSession).filter(PaymentSession.session_code == expired_code).first()
        new_check = db.query(PaymentSession).filter(PaymentSession.session_code == new_code).first()
        
        assert old_check.status == "EXPIRED"
        assert new_check.status == "PENDING"
        assert new_check.amount == 39.0
        
        # Verify new expiry is exactly 10 minutes from now (Task 10.1 & 10.6)
        time_diff = (new_check.expires_at - datetime.utcnow()).total_seconds()
        assert 590 < time_diff <= 600 # Should be very close to 600s
        print(f"[OK] New session strictly capped at 10 minutes ({time_diff:.1f}s remaining)")

        db.close()

    print("=== Task 10 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_10())
