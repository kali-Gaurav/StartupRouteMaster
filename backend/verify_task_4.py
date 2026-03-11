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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("turbo-verify")

async def test_turbo_router():
    print("\n🚀 [TASK 4 DEEP VERIFICATION] TurboRouter (Binary 1-Transfer)")
    print("="*60)
    
    await initialize_database_pools()
    router = TurboRouter()
    
    test_pairs = [
        ("NDLS", "MMCT"),  # Direct should also be found
        ("PGT", "KOTA"),   # Likely needs a transfer
        ("SBC", "NZM"),    # Bangalore to Delhi
        ("MAS", "HWH")     # Chennai to Kolkata
    ]
    
    departure_date = datetime.now()
    
    for src, dst in test_pairs:
        print(f"\n🔍 Searching: {src} -> {dst}...")
        start = asyncio.get_event_loop().time()
        routes = router.find_routes(src, dst, departure_date)
        lat = (asyncio.get_event_loop().time() - start) * 1000
        
        if routes:
            print(f"✅ Success: Found {len(routes)} routes in {lat:.2f}ms")
            # Analyze first route
            top = routes[0]
            if top['type'] == 'direct':
                print(f"   [DIRECT] Train {top['train_no']}: {top['dep']} -> {top['arr']}")
            else:
                print(f"   [1-TRANSFER] Via {top['hub']}")
                print(f"     Leg 1: {top['legs'][0]['train']} ({top['legs'][0]['from']}->{top['legs'][0]['to']}) {top['legs'][0]['dep']}->{top['legs'][0]['arr']}")
                print(f"     Leg 2: {top['legs'][1]['train']} ({top['legs'][1]['from']}->{top['legs'][1]['to']}) {top['legs'][1]['dep']}->{top['legs'][1]['arr']}")
        else:
            print(f"⚠️ No routes found for {src}->{dst}.")

    print("\n" + "="*60)
    print("✅ TurboRouter Verification Finished.")

if __name__ == "__main__":
    asyncio.run(test_turbo_router())
