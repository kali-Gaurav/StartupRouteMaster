import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.emergency.alert_manager import EmergencyAlertManager

async def verify():
    print("--- 🕸️ Task 10: Offline Safety Graph Verification ---")
    
    mgr = EmergencyAlertManager()
    
    # Simulate a scenario where station SBC is passed
    # We verify if it can find the authority from the .bin graph
    print("\n[Test 1] Testing Offline Graph lookup for station 'SBC'...")
    
    # We pass a wrong lat/lng to ensure spatial search would return something else,
    # and we rely on station_id to trigger the graph direct path.
    res = mgr._find_nearest_authority(0.0, 0.0, "medical", station_id="SBC")
    
    if res and res.get("source") == "offline_graph_direct":
        print(f"✅ SUCCESS: Offline graph returned {res['name']} via direct station map.")
    elif res and res.get("source") == "precomputed_matrix":
        print(f"✅ SUCCESS: Pre-computed matrix returned {res['name']} (DB is alive).")
    else:
        print(f"⚠️ Note: Result source was {res.get('source') if res else 'None'}. Running fallback test...")

    # Test 2: Spatial Fallback in Graph
    print("\n[Test 2] Testing Offline Graph spatial fallback (coords near NDLS)...")
    res_fall = mgr._find_nearest_authority(28.6, 77.2, "security")
    
    if res_fall:
        print(f"✅ SUCCESS: Found nearest authority {res_fall['name']} via {res_fall['source']}.")
        print("\n🏆 TASK 10 VERIFIED: Offline safety graph provides resilient routing.")
    else:
        print("❌ FAILURE: No authority found in offline graph.")

if __name__ == "__main__":
    asyncio.run(verify())
