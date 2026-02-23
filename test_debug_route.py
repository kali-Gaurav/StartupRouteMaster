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
from backend.core.route_engine import route_engine
from backend.database.models import Stop
from backend.core.route_engine.constraints import RouteConstraints

async def test_raptor_directly():
    db = SessionLocal()
    try:
        # Check if NDLS and BCT exist in DB
        s_ndls = db.query(Stop).filter(Stop.code == "NDLS").first()
        s_bct = db.query(Stop).filter(Stop.code == "BCT").first()
        print(f"NDLS: {s_ndls.name if s_ndls else 'NOT FOUND'} (ID: {s_ndls.id if s_ndls else 'N/A'})")
        print(f"BCT: {s_bct.name if s_bct else 'NOT FOUND'} (ID: {s_bct.id if s_bct else 'N/A'})")

        if not s_ndls or not s_bct:
            print("Cannot proceed - missing stations")
            return

        travel_date = datetime(2026, 3, 25, 12, 0, 0)
        constraints = RouteConstraints(max_transfers=3, range_minutes=1440)
        
        print(f"\n=== Direct RAPTOR Call ===")
        print(f"Source ID: {s_ndls.id}, Dest ID: {s_bct.id}")
        print(f"Travel Date: {travel_date}")
        
        # Call RAPTOR directly
        routes = await route_engine.raptor.find_routes(
            source_stop_id=s_ndls.id,
            dest_stop_id=s_bct.id,
            departure_date=travel_date,
            constraints=constraints,
            graph=None
        )
        
        print(f"\n=== RAPTOR Result ===")
        print(f"Found {len(routes)} routes")
        
        for i, route in enumerate(routes):
            print(f"\nRoute {i+1}:")
            print(f"  Segments: {len(route.segments)}")
            print(f"  Duration: {route.total_duration} min")
            print(f"  Cost: {route.total_cost}")
            print(f"  Score: {route.score}")
            if route.segments:
                print(f"  From: {route.segments[0].departure_stop_id} To: {route.segments[-1].arrival_stop_id}")
        
    finally:
        db.close()

asyncio.run(test_raptor_directly())
