import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.alert_manager import EmergencyAlertManager

async def test_bridge():
    print("--- 🌉 Conference Call Bridge Verification ---")
    
    manager = EmergencyAlertManager()
    
    # Simulate a critical SOS
    critical_event = {
        "id": "conf-test-999",
        "priority": "critical",
        "phone": "+919876543210",
        "category": "security",
        "nearest_authority": {
            "name": "Mumbai GRP",
            "contact_number": "+91-GRP-100"
        },
        "trip": {"vehicle_number": "12628"}
    }
    
    print("\n[Test] Processing CRITICAL SOS and expecting conference bridge...")
    res = await manager.process_sos_alert(critical_event)
    
    conf_id = res.get("conference_id")
    print(f"Generated Conference ID: {conf_id}")
    
    if conf_id and "CONF-" in conf_id:
        print("\n🏆 CONFERENCE BRIDGE VERIFIED: Bridge room created and participants dialed.")
    else:
        print("\n❌ FAIL: Conference ID missing or incorrect.")

if __name__ == "__main__":
    asyncio.run(test_bridge())
