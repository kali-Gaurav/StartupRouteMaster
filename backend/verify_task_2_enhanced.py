import sys
import os
import httpx
import asyncio
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def verify_task_2():
    print("=== Verifying Task 2: Real-Time Bank SMS/Webhook Integration ===")
    
    # 1. Simulate a Bank SMS Webhook
    # Body: "HDFC Bank: Rs 500.00 transferred to VPA Ref 987654321098"
    payload = {
        "sender": "AD-HDFCBK",
        "body": "HDFC Bank: Rs 500.00 transferred to VPA Ref 987654321098",
        "timestamp": datetime.utcnow().isoformat(),
        "device_id": "DEVICE_001"
    }
    
    async with httpx.AsyncClient() as client:
        print("Sending simulated bank SMS webhook...")
        response = await client.post(
            "http://localhost:8000/api/bank_webhook/sms",
            json=payload,
            timeout=10
        )
        
    print(f"Response: {response.status_code} - {response.text}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["utr"] == "987654321098"
    print("[OK] SMS Parsing & Webhook Reception")

    # 2. Test Duplicate Filtering
    async with httpx.AsyncClient() as client:
        print("Sending duplicate UTR...")
        response = await client.post(
            "http://localhost:8000/api/bank_webhook/sms",
            json=payload
        )
    data = response.json()
    assert data["success"] is False
    assert "Duplicate UTR" in data["message"]
    print("[OK] Duplicate UTR Filtering")

    print("=== Task 2 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_2())
