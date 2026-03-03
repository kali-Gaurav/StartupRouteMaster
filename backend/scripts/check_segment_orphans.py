from database.session import SessionLocal
from sqlalchemy import text
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

def check_orphans():
    session = SessionLocal()
    try:
        total = session.execute(text("SELECT count(*) FROM segments")).scalar()
        matched = session.execute(text("SELECT count(*) FROM segments s JOIN trips t ON CAST(s.trip_id AS INTEGER) = t.id")).scalar()
        
        print(f"Total Segments: {total}")
        print(f"Segments with matching Trip: {matched}")
        print(f"Segments orphaned: {total - matched}")
        
        if total - matched > 0:
            print("Sample orphaned trip_ids from segments:")
            orphans = session.execute(text("SELECT DISTINCT trip_id FROM segments s LEFT JOIN trips t ON CAST(s.trip_id AS INTEGER) = t.id WHERE t.id IS NULL LIMIT 5")).fetchall()
            for o in orphans:
                print(f"  - {o[0]}")
                
        # Also check trips without segments
        trips_total = session.execute(text("SELECT count(*) FROM trips")).scalar()
        
        # We need to handle the case where trip_id might not be castable to int if it has letters, 
        # but in our DB it seems they are numeric strings or the casting would fail above.
        try:
            trips_with_segs = session.execute(text("SELECT count(DISTINCT CAST(trip_id AS INTEGER)) FROM segments")).scalar()
        except:
            trips_with_segs = session.execute(text("SELECT count(DISTINCT trip_id) FROM segments")).scalar()
            
        print(f"Total Trips in DB: {trips_total}")
        print(f"Trips with at least one segment: {trips_with_segs}")
        
    finally:
        session.close()

if __name__ == "__main__":
    check_orphans()
