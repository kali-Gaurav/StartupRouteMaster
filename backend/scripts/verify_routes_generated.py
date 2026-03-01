import asyncio
import os
import sys
import json
from datetime import datetime

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from database.session import SessionLocal
from services.search_service import SearchService
from core.route_engine import route_engine

async def test_route_generation():
    print("🚀 Initializing Route Engine...")
    await route_engine.initialize()
    
    db = SessionLocal()
    service = SearchService(db)
    
    source = "NDLS"
    destination = "MTJ"
    date = "2026-05-15"
    
    print(f"📡 Searching routes for {source} -> {destination} on {date}...")
    from utils.station_utils import resolve_stations
    src_s, dst_s = resolve_stations(db, source, destination)
    print(f"DEBUG: Resolved {source} to ID={getattr(src_s, 'id', 'NONE')} Code={getattr(src_s, 'code', 'NONE')} stop_id={getattr(src_s, 'stop_id', 'NONE')}")
    print(f"DEBUG: Resolved {destination} to ID={getattr(dst_s, 'id', 'NONE')} Code={getattr(dst_s, 'code', 'NONE')} stop_id={getattr(dst_s, 'stop_id', 'NONE')}")
    
    start_time = datetime.now()
    
    result = await service.search_routes(
        source=source,
        destination=destination,
        travel_date=date,
        budget_category="standard"
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    print(f"⏱️ Search took {duration:.2f}s")
    
    if "journeys" in result:
        journeys = result["journeys"]
        print(f"✅ SUCCESS: Generated {len(journeys)} routes!")
        for i, j in enumerate(journeys[:5]):
            print(f"  [{i+1}] {j['travel_time']}h | ₹{j['total_cost']} | {j['availability_status']}")
            for leg in j['legs']:
                print(f"      - Train {leg['train_number']}: {leg['from_station_code']} -> {leg['to_station_code']}")
    else:
        print("❌ FAILED: No routes found in result dictionary.")
        print(f"Result keys: {result.keys()}")
        if "message" in result:
            print(f"Error Message: {result['message']}")

    db.close()

if __name__ == "__main__":
    asyncio.run(test_route_generation())
