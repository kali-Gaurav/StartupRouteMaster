import asyncio
import logging
import sys
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine.builder import GraphBuilder
from database.session import SessionLocal
from database.models import Trip

async def find_missing_trips():
    executor = ThreadPoolExecutor(max_workers=1)
    builder = GraphBuilder(executor)
    target_date = datetime.now()
    
    session = SessionLocal()
    # Get all trips that SHOULD be active today
    active_service_ids = builder._get_active_service_ids(session, target_date)
    expected_trip_ids = [r[0] for r in session.query(Trip.id).filter(Trip.service_id.in_(active_service_ids)).all()]
    session.close()
    
    print(f"Expected Trips in DB for today: {len(expected_trip_ids)}")
    
    graph_data = await builder.build_graph(target_date)
    indexed_trip_ids = list(graph_data.snapshot.trip_segments.keys())
    
    print(f"Indexed Trips in Graph: {len(indexed_trip_ids)}")
    
    missing = set(expected_trip_ids) - set(indexed_trip_ids)
    if missing:
        print(f"Found {len(missing)} missing trips: {list(missing)[:20]}")
        
        # Analyze why one is missing
        session = SessionLocal()
        from sqlalchemy import text
        for tid in list(missing)[:3]:
            res = session.execute(text(f"SELECT count(*) FROM stop_times WHERE trip_id = {tid}")).scalar()
            print(f"Trip ID {tid}: has {res} stop_times in DB")
            
            # Check segments
            seg_res = session.execute(text(f"SELECT count(*) FROM segments WHERE CAST(trip_id AS INTEGER) = {tid}")).scalar()
            print(f"Trip ID {tid}: has {seg_res} segments in DB")
        session.close()
    else:
        print("No trips missing from graph.")

if __name__ == "__main__":
    asyncio.run(find_missing_trips())
