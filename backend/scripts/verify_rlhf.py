import httpx
import asyncio
import json
from sqlalchemy.orm import Session
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database import SessionLocal
from database.models import RLFeedbackLog

async def test_rlhf():
    url = "http://localhost:8000/api/chat/feedback"
    print("--- RLHF Feedback Loop Verification ---")
    
    payload = {
        "session_id": "test-rlhf-session",
        "prompt": "How are you?",
        "response": "I am Diksha, your travel assistant.",
        "rating": 1
    }
    
    # 1. Send Feedback
    print(f"\n[Test 1] Sending positive feedback...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10.0)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
            
            # 2. Verify in DB
            db = SessionLocal()
            log = db.query(RLFeedbackLog).filter(RLFeedbackLog.prompt == payload["prompt"]).first()
            
            if log and log.rating == 1:
                print("[PASS] Feedback correctly saved in database.")
            else:
                print("[FAIL] Feedback not found or incorrect in DB.")
            db.close()
                
        except Exception as e:
            print(f"Error: {e}")
            print("Note: Ensure the backend server is running on port 8000.")

if __name__ == "__main__":
    asyncio.run(test_rlhf())
