import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.getcwd()))

from services.search.main import search_service
from core.data_structures import RoutingRequest, RouteConstraints

async def main():
    print("🧬 [GRAND_JUMP] Initializing Stress Test...")
    
    constraints = RouteConstraints(max_transfers=3, timeout_ms=5000)
    
    print("🔍 [GRAND_JUMP] Requesting: KOTA -> BLR (Multimodal Jump)")
    
    try:
        results = await search_service.search(
            source="KOTA",
            destination="BLR",
            travel_date=datetime.now() + timedelta(days=2),
            constraints=constraints,
            use_interlining=True
        )
        
        print(f"📊 [GRAND_JUMP] Found {len(results)} total routes.")
        
        interlined = [r for r in results if r.get("metadata", {}).get("type") == "VIRTUAL_INTERLINED"]
        
        if interlined:
            print(f"✅ [SUCCESS] Found {len(interlined)} Virtual Interlined routes!")
            for i, r in enumerate(interlined[:3]):
                modes = r.get("metadata", {}).get("modes", [])
                print(f"   [{i}] Mode: {' + '.join(modes)} | Cost: {r.get('total_cost')} | Duration: {r.get('total_duration')}m")
        else:
            print("❌ [FAILURE] No interlined routes found. Check InterliningEngine hub radius (35km) and Mocks.")

    except Exception as e:
        print(f"💥 [ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
