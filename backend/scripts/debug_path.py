import asyncio
import sys
import os
import uuid
from datetime import datetime
import sqlite3

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.session import SessionLocal, SessionTransit
from database.models import StopTime, Stop, TrainLiveUpdate
from services.emergency.safety_service import safety_service

async def debug_path():
    db_transit = SessionTransit()
    
    # 1. Train 12561 at NDLS (Sequence 1 usually)
    train_no = '12561'
    
    # Get current sequence for this train in DB
    ndls = db_transit.query(Stop).filter(Stop.code == 'NDLS').first()
    
    # Find sequence of NDLS for a trip of this train
    res = db_transit.query(StopTime.trip_id, StopTime.stop_sequence)\
        .filter(StopTime.stop_id == ndls.id).first()
    
    if not res:
        print("No trip found.")
        return
        
    trip_id, seq = res
    print(f"Train {train_no}, Trip {trip_id}, NDLS Sequence: {seq}")
    
    # Get stops in focus area (seq - 1 to seq + 1)
    stops = db_transit.query(Stop.code, Stop.latitude, Stop.longitude)\
        .join(StopTime, Stop.id == StopTime.stop_id)\
        .filter(StopTime.trip_id == trip_id, StopTime.stop_sequence.between(seq-1, seq+1)).all()
    
    print("\nStops in focus area:")
    for s in stops:
        dist = safety_service.haversine(ndls.latitude, ndls.longitude, s.latitude, s.longitude)
        print(f"Stop: {s.code}, Coords: ({s.latitude}, {s.longitude}), Dist from NDLS: {dist:.2f}km")

if __name__ == "__main__":
    asyncio.run(debug_path())
