import asyncio
import json
import os
import sys
from datetime import datetime, timedelta

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.search_service import SearchService
from database.session import SessionLocal

async def main():
    print("🚀 Real Search Integration Test (PGT -> BNC)...")
    
    db = SessionLocal()
    search_svc = SearchService(db)
    
    source = "PGT"
    destination = "BNC"
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"🔍 Searching routes for {source} -> {destination} on {tomorrow}...")
    
    # This will trigger TurboRouter -> SearchService -> SeatVerification (Deferred usually)
    # But for verification testing, we want to see if the search service finds the routes correctly
    results = await search_svc.search_routes(source, destination, tomorrow)
    
    print(f"✨ Found {len(results.get('journeys', []))} journeys.")
    
    if results.get('journeys'):
        first = results['journeys'][0]
        print(f"   [1] Journey ID: {first['journey_id']}")
        print(f"       Segments: {len(first['legs'])}")
        for leg in first['legs']:
            print(f"       - Train {leg['train_number']}: {leg['from_station_code']} -> {leg['to_station_code']}")
    
    # Save search result to file for inspection
    with open("real_search_output.json", "w") as f:
        json.dump(results, f, indent=4)
    print("💾 Search output saved to real_search_output.json")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
