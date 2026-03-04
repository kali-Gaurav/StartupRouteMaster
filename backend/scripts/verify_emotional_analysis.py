import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.emergency.alert_manager import EmergencyAlertManager

async def test_emotional_analysis():
    print("--- 🧠 Emotional State Analysis Verification ---")
    
    manager = EmergencyAlertManager()
    
    # 1. Test High Panic
    panicked_event = {
        "id": "panic-test-1",
        "lat": 0, "lng": 0,
        "extra": "User is screaming",
        "chat_history": [
            {"role": "user", "content": "PLEASE SAVE ME I AM DYING HELP HELP!!!"}
        ]
    }
    
    print("\n[Test 1] Processing highly panicked SOS...")
    res1 = await manager.process_sos_alert(panicked_event)
    print(f"Panic Score: {res1.get('panic_score')}")
    print(f"Priority: {res1.get('priority')}")
    
    if res1.get("panic_score") >= 8 and res1.get("priority") == "critical":
        print("[PASS] High panic correctly detected and priority escalated.")
    else:
        print("[FAIL] Panic detection mismatch.")

    # 2. Test Moderate Concern
    calm_event = {
        "id": "calm-test-1",
        "lat": 0, "lng": 0,
        "extra": "Inquiry",
        "chat_history": [
            {"role": "user", "content": "I am a bit worried about my luggage."}
        ]
    }
    
    print("\n[Test 2] Processing moderate concern SOS...")
    res2 = await manager.process_sos_alert(calm_event)
    print(f"Panic Score: {res2.get('panic_score')}")
    print(f"Priority: {res2.get('priority')}")
    
    if res2.get("panic_score") < 5:
        print("[PASS] Calm/Moderate concern assigned lower panic score.")
    else:
        print("[FAIL] Emotional analysis too sensitive.")

if __name__ == "__main__":
    asyncio.run(test_emotional_analysis())
