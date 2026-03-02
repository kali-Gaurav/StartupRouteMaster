import asyncio
import json
import os
from database.session import SessionLocal
from services.search_service import SearchService

async def test():
    db = SessionLocal()
    s = SearchService(db)
    # Search PGT to KOTA for tomorrow (Tuesday)
    res = await s.search_routes('PGT', 'KOTA', '2026-03-03', force_refresh=True)
    
    print(f"Total Routes Found (Before Filter): {res.get('total_available', 0)}")
    print(f"Valid Journeys (After Schedule Filter): {len(res.get('journeys', []))}")
    
    for idx, j in enumerate(res.get('journeys', [])):
        print(f"\nJourney {idx+1}: {j['journey_id']} | Engine: {j['engine_used']}")
        for leg in j['legs']:
            print(f"  - Train {leg['train_number']} ({leg['train_name']}): {leg['from_station_code']}->{leg['to_station_code']} | Verified: {j.get('is_verified')}")
        print(f"  Confidence: {j.get('confidence_score')}% | Status: {j.get('availability_status')}")
        
    db.close()

if __name__ == "__main__":
    asyncio.run(test())
