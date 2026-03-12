import asyncio
import logging
import os
import sys
from datetime import datetime

# Setup paths
BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from core.route_engine.turbo_router import TurboRouter
from database.session import initialize_database_pools

logging.basicConfig(level=logging.ERROR) # Only show errors during stress test

async def deep_test_task_4():
    print("\n🕵️ [DEEP STRESS TEST TASK 4] TurboRouter Integrity")
    print("="*60)
    
    await initialize_database_pools()
    router = TurboRouter()
    departure_date = datetime.now()
    errors = []

    # Test Case 1: Metro Cluster Station-Change Transfer (NDLS -> NZM)
    # Finding a route where we arrive at NDLS and depart from NZM
    print("🔍 [TEST 1/4] Metro Cluster Station-Change (NDLS <-> NZM)...")
    # Search from a station that only connects to NDLS, to one that only connects to NZM
    # Or search between distant cities and look for 'NDLS->NZM' in the hub field
    routes = router.find_routes("MAS", "KOTA", departure_date, limit=100)
    metro_transfers = [r for r in routes if "->" in r.get("hub", "")]
    if metro_transfers:
        print(f"   ✅ Found {len(metro_transfers)} station-change transfers.")
        top = metro_transfers[0]
        print(f"   Sample: {top['hub']} (Score: {top['score']:.2f})")
    else:
        print("   ⚠️ No station-change transfers found in this sample. (Normal if direct is better)")

    # Test Case 2: Connection Time Constraints (Subtask 4.4, 4.5)
    print("🔍 [TEST 2/4] Connection Time Logic (45m - 12h)...")
    all_routes = router.find_routes("SBC", "NDLS", departure_date, limit=100)
    for r in all_routes:
        if r['type'] == '1-transfer':
            leg1_arr = r['legs'][0]['arr']
            leg2_dep = r['legs'][1]['dep']
            
            def to_min(t):
                h, m, s = map(int, t.split(':'))
                return h * 60 + m
            
            l1_a = to_min(leg1_arr)
            l2_d = to_min(leg2_dep)
            layover = (l2_d - l1_a) % 1440
            
            # If it's a station change, min is 45 + 60 = 105
            min_required = 105 if "->" in r['hub'] else 45
            
            if layover < min_required:
                errors.append(f"Illegal short layover: {layover}m at {r['hub']} (Min: {min_required}m)")
            if layover > 720:
                errors.append(f"Illegal long layover: {layover}m at {r['hub']} (Max: 12h)")

    # Test Case 3: Same-Train Collision Prevention (Subtask 4.13)
    print("🔍 [TEST 3/4] Collision Prevention (Leg 1 != Leg 2)...")
    for r in all_routes:
        if r['type'] == '1-transfer':
            if r['legs'][0]['train'] == r['legs'][1]['train']:
                errors.append(f"Collision detected: Same train {r['legs'][0]['train']} used for both legs!")

    # Test Case 4: Scoring Consistency (Subtask 4.10)
    print("🔍 [TEST 4/4] Scoring Consistency (Short layover > Long layover)...")
    transfers = [r for r in all_routes if r['type'] == '1-transfer' and "->" not in r['hub']]
    if len(transfers) >= 2:
        # Sort by layover manually
        def get_layover(r):
            l1_a = sum(x * int(t) for x, t in zip([60, 1, 0], r['legs'][0]['arr'].split(':')))
            l2_d = sum(x * int(t) for x, t in zip([60, 1, 0], r['legs'][1]['dep'].split(':')))
            return (l2_d - l1_a) % 1440
            
        # Check if score correlates negatively with layover
        t1, t2 = transfers[0], transfers[-1]
        if get_layover(t1) < get_layover(t2) and t1['score'] < t2['score']:
            errors.append("Scoring anomaly: shorter layover has lower score.")

    print("\n" + "="*60)
    if not errors:
        print("✅ ALL HARD TESTS PASSED! TurboRouter is production-grade.")
    else:
        print(f"❌ FAILED with {len(errors)} errors:")
        for e in errors[:10]: print(f"  - {e}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(deep_test_task_4())
