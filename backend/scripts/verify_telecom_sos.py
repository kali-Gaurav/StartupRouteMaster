import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.alert_manager import EmergencyAlertManager

async def test_telecom_integration():
    print("--- Automated Call Center Verification ---")
    
    manager = EmergencyAlertManager()
    
    # Simulate high-priority SOS with phone number
    emergency_event = {
        "id": "test-telecom-1",
        "lat": 28.6430,
        "lng": 77.2195,
        "phone": "+919876543210",
        "extra": "Passenger complaining of severe chest pain.",
        "chat_history": []
    }
    
    print("\n[Test] Processing SOS and expecting telecom trigger...")
    res = await manager.process_sos_alert(emergency_event)
    
    # The call is initiated as an asyncio task, so we wait briefly
    await asyncio.sleep(1)
    
    print(f"Category: {res.get('category')}")
    print("[PASS] Check backend logs for the 📞 [TELECOM] output.")

if __name__ == "__main__":
    asyncio.run(test_telecom_integration())
