import asyncio
import logging
import os
import sys
from datetime import date, timedelta

# Setup paths
BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from core.route_engine.ultra_turbo import UltraTurboDirectEngine
from database.session import initialize_database_pools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ultra-turbo-verify")

async def test_ultra_turbo():
    print("\n🚀 [TASK 3 DEEP VERIFICATION] Ultra-Turbo Direct Engine")
    print("="*60)
    
    await initialize_database_pools()
    engine = UltraTurboDirectEngine()
    
    test_pairs = [
        ("NDLS", "MMCT"), # Delhi to Mumbai
        ("MAS", "SBC"),   # Chennai to Bangalore
        ("HWH", "HWH"),   # Same station (Test 3.13)
        ("CSMT", "KYN"),  # Mumbai local
        ("NZM", "KOTA"),  # Delhi to Kota
        ("NDLS", "PGT")   # Long distance
    ]
    
    travel_date = date.today() + timedelta(days=5)
    
    for src, dst in test_pairs:
        print(f"\n🔍 Searching: {src} -> {dst} on {travel_date}")
        start = asyncio.get_event_loop().time()
        routes = await engine.find_routes(src, dst, travel_date)
        lat = (asyncio.get_event_loop().time() - start) * 1000
        
        if src == dst:
            if not routes:
                print(f"✅ Same station check passed (0 routes).")
            else:
                print(f"❌ Same station check failed! ({len(routes)} routes found)")
            continue

        if routes:
            print(f"✅ Success: Found {len(routes)} direct routes in {lat:.2f}ms")
            best = routes[0]
            seg = best.segments[0]
            print(f"   Top Result: Train {seg.train_number}, Score: {best.score}")
            print(f"   Distance: {seg.distance_km} km, Duration: {seg.duration_minutes} min")
            print(f"   Platforms: {seg.metadata.get('platform')} -> {seg.metadata.get('dest_platform')}")
            
            # Verify Subtask 3.4/3.8 (Non-zero dist/dur)
            if seg.distance_km <= 0 or seg.duration_minutes <= 0:
                print(f"❌ Error: Invalid distance/duration in segments!")
        else:
            print(f"⚠️ No routes found (Might be no direct trains on this specific day).")

    print("\n" + "="*60)
    print("✅ Deep Verification Finished.")

if __name__ == "__main__":
    asyncio.run(test_ultra_turbo())
