import asyncio
import sys
import os
from datetime import datetime
from sqlalchemy.orm import Session

import logging

# Configure logging to see DEBUG output
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add current directory to path
sys.path.append(os.getcwd())

from backend.database import SessionLocal
from backend.database.config import Config
from backend.services.search_service import SearchService
from backend.core.route_engine import route_engine
from backend.database.models import Stop

async def test_search():
    print(f"DEBUG: Config.DATABASE_URL = {Config.DATABASE_URL}")
    db = SessionLocal()
    try:
        # Check if NDLS and BCT exist in DB
        s_ndls = db.query(Stop).filter(Stop.code == "NDLS").first()
        s_bct = db.query(Stop).filter(Stop.code == "BCT").first()
        print(f"DEBUG: NDLS found: {s_ndls.name if s_ndls else 'NO'}")
        print(f"DEBUG: BCT found: {s_bct.name if s_bct else 'NO'}")

        service = SearchService(db, route_engine_instance=route_engine)
        
        source = "NDLS"
        destination = "BCT"
        travel_date = "2026-03-25 12:00:00" # Wednesday, centered at noon
        
        print(f"Testing Search: {source} -> {destination} on {travel_date}")
        
        result = await service.search_routes(
            source=source,
            destination=destination,
            travel_date=travel_date
        )
        
        print("\nSearch Results Summary:")
        print(f"Source: {result.get('source')}")
        print(f"Destination: {result.get('destination')}")
        print(f"Message: {result.get('journey_message')}")
        
        routes = result.get('routes', {})
        print(f"Direct Routes: {len(routes.get('direct', []))}")
        print(f"One Transfer: {len(routes.get('one_transfer', []))}")
        
        if routes.get('direct'):
            for i, r in enumerate(routes['direct'][:3]):
                print(f"\nDirect Route {i+1}: {r.get('train_no')} {r.get('train_name')}")
                print(f"Departure: {r.get('departure')}, Arrival: {r.get('arrival')}")
                print(f"Duration: {r.get('time_str')}, Fare: {r.get('fare')}")
            
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Test Failed with error: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = asyncio.run(test_search())
    sys.exit(0 if success else 1)
