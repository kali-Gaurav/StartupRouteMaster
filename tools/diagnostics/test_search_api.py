import sys
import os
from pathlib import Path

# Add backend to sys.path so we can import 'services', 'database', etc.
root = Path(__file__).resolve().parent
backend_path = str(root / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# IMPORT CONSISTENTLY! Use 'database.session', NOT 'backend.database.session'
from services.search_service import SearchService
from database.session import SessionLocal, initialize_database_pools
from core.route_engine.engine import route_engine as engine
import asyncio

async def test_search():
    # Initialize DB pools
    await initialize_database_pools()
    
    db = SessionLocal()
    service = SearchService(db, route_engine_instance=engine)
    
    source = "NDLS"
    destination = "CSMT"
    travel_date = "2026-05-10"
    
    print(f"Searching for routes from {source} to {destination} on {travel_date}...")
    try:
        result = await service.search_routes(
            source=source,
            destination=destination,
            travel_date=travel_date,
            limit=5
        )
        print(f"Status: {result.status}")
        print(f"Found {result.count} routes.")
        for i, route in enumerate(result.routes):
            print(f"Route {i+1}:")
            for seg in route.segments:
                print(f"  {seg.train_number} {seg.departure_code}->{seg.arrival_code} ({seg.departure_time} - {seg.arrival_time})")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_search())
