import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.emergency.connectivity_service import connectivity_service

async def verify():
    print("--- 📡 Signal Dead-Zone Awareness Verification ---")
    
    # Coordinates near Western Ghats Tunnel (19.7, 73.4)
    # Testing 5km away
    test_lat = 19.72
    test_lng = 73.42
    
    zones = connectivity_service.check_upcoming_dead_zones(test_lat, test_lng)
    
    if zones:
        zone = zones[0]
        print(f"Approaching Dead Zone: {zone['description']}")
        print(f"Distance: {zone['distance_km']} km")
        print(f"Expected Duration: {zone['expected_duration_mins']} mins")
        print(f"Imminent: {zone['is_imminent']}")
        
        if zone['id'] == 'tunnel-1' and zone['distance_km'] < 10:
             print("\n🏆 DEAD-ZONE AWARENESS VERIFIED: Tunnel detected correctly.")
        else:
             print("\n❌ DEAD-ZONE AWARENESS FAILED: Unexpected zone data.")
    else:
        print("❌ No dead zones detected. Ensure the database has seeded signal_dead_zones.")

if __name__ == "__main__":
    asyncio.run(verify())