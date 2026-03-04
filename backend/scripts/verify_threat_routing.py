import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.alert_manager import EmergencyAlertManager

async def test_threat_routing():
    print("--- Threat Classification & Authority Routing Verification ---")
    
    manager = EmergencyAlertManager()
    
    # 1. Simulate Security SOS near Mumbai Central
    security_event = {
        "id": "test-sec-1",
        "lat": 18.9690,
        "lng": 72.8190,
        "extra": "User clicked SOS widget",
        "chat_history": [
            {"role": "user", "content": "Help me, someone is trying to snatch my bag!"}
        ]
    }
    
    print("\n[Test 1] Processing Security SOS (Bag Snatching near BCT)...")
    res1 = await manager.process_sos_alert(security_event)
    
    print(f"Detected Category: {res1.get('category')}")
    nearest1 = res1.get('nearest_authority', {})
    print(f"Routed To: {nearest1.get('name')} ({nearest1.get('type')}) - {nearest1.get('distance_km')}km away")
    
    if res1.get('category') == 'security' and nearest1.get('type') == 'GRP':
        print("[PASS] Security threat correctly classified and routed to GRP.")
    else:
        print("[FAIL] Security classification or routing failed.")

    # 2. Simulate Medical SOS near New Delhi
    medical_event = {
        "id": "test-med-1",
        "lat": 28.6430,
        "lng": 77.2195,
        "extra": "Passenger complaining of severe chest pain.",
        "chat_history": []
    }
    
    print("\n[Test 2] Processing Medical SOS (Chest pain near NDLS)...")
    res2 = await manager.process_sos_alert(medical_event)
    
    print(f"Detected Category: {res2.get('category')}")
    nearest2 = res2.get('nearest_authority', {})
    print(f"Routed To: {nearest2.get('name')} ({nearest2.get('type')}) - {nearest2.get('distance_km')}km away")
    
    if res2.get('category') == 'medical' and nearest2.get('type') == 'HOSPITAL':
        print("[PASS] Medical threat correctly classified and routed to Hospital.")
    else:
        print("[FAIL] Medical classification or routing failed.")

if __name__ == "__main__":
    asyncio.run(test_threat_routing())
