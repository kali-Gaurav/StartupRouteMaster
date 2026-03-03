from database.session import SessionLocal
from database.models import Trip, StopTime, Segment
from sqlalchemy import func
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

def audit_data():
    session = SessionLocal()
    try:
        trips_count = session.query(Trip).count()
        stop_times_trips = session.query(func.count(func.distinct(StopTime.trip_id))).scalar()
        segments_trips = session.query(func.count(func.distinct(Segment.trip_id))).scalar()
        
        print(f"Trips in 'trips' table: {trips_count}")
        print(f"Unique trips in 'stop_times' table: {stop_times_trips}")
        print(f"Unique trips in 'segments' table: {segments_trips}")
        
        # Check if stop_times trip_ids match trips.id
        matched_st = session.query(func.count(func.distinct(StopTime.trip_id))).filter(StopTime.trip_id <= trips_count).scalar()
        print(f"StopTimes trips matching a 'trips' record: {matched_st}")
        
    finally:
        session.close()

if __name__ == "__main__":
    audit_data()
