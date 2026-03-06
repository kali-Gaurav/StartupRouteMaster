import sys
import os
import uuid
import httpx
import asyncio

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionLocal
from database.models import PaymentSession, User

def setup_mock_session():
    db = SessionLocal()
    try:
        user_id = str(uuid.uuid4())
        user = User(id=user_id, email=f"test9_{user_id}@example.com")
        db.add(user)
        db.commit() # Commit here to satisfy FK constraint
        
        session_code = str(uuid.uuid4().hex[:6]).upper()
        session = PaymentSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_code=session_code,
            amount=50.0,
            status="PENDING"
        )
        db.add(session)
        db.commit()
        return session_code
    finally:
        db.close()

async def verify_task_9():
    print("=== Verifying Task 9: Mobile Deep-Link Detector (Backend) ===")
    
    session_code = setup_mock_session()
    
    async with httpx.AsyncClient() as client:
        # 1. Test Intent Generation
        print("Testing Intent Generation Endpoint...")
        response = await client.get(f"http://localhost:8000/api/payment/intents/{session_code}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        intents = data["intents"]
        assert "gpay" in intents
        assert "intent://pay?" in intents["gpay"]
        assert "com.google.android.apps.nbu.paisa.user" in intents["gpay"]
        
        assert "phonepe" in intents
        assert "intent://pay?" in intents["phonepe"]
        assert "com.phonepe.app" in intents["phonepe"]
        print("[OK] Android Intents correctly generated")
        
        # 2. Test Click Analytics
        print("Testing Click Analytics Tracking...")
        payload = {
            "session_code": session_code,
            "selected_app": "phonepe",
            "device_os": "android"
        }
        res_analytics = await client.post("http://localhost:8000/api/payment/analytics/click", json=payload)
        print(f"Analytics Response: {res_analytics.status_code} - {res_analytics.text}")
        assert res_analytics.status_code == 200
        assert res_analytics.json()["success"] is True
        print("[OK] Click Analytics tracked successfully")

    print("=== Task 9 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_9())
