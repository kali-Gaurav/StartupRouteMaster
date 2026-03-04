import asyncio
import sys
import os
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.session import SessionLocal, SessionTransit
from database.models import User, Booking, Trip, Stop, StopTime, Route, TrainLiveUpdate
from services.emergency.safety_service import safety_service

async def test_deviation_engine():
    db_user = SessionLocal()
    db_transit = SessionTransit()
    user_id = str(uuid.uuid4())
    
    print("--- Safety Deviation Engine Verification ---")
    
    try:
        # 1. Setup Test Data
        ndls = db_transit.query(Stop).filter(Stop.code == 'NDLS').first()
        bct = db_transit.query(Stop).filter(Stop.code == 'BCT').first()
        if not ndls or not bct:
            print("[SKIP] NDLS or BCT station not found.")
            return

        # Find a trip between NDLS and BCT
        trip_id_res = db_transit.query(StopTime.trip_id).filter(StopTime.stop_id == ndls.id).first()
        trip_id = trip_id_res[0]
        
        # Get train number
        train_info = db_transit.query(Route.route_id).join(Trip, Route.id == Trip.route_id).filter(Trip.id == trip_id).first()
        train_no = train_info[0]

        user = User(id=user_id, email=f"safety_{user_id[:8]}@example.com")
        pnr = str(uuid.uuid4())[:10]
        booking = Booking(
            id=str(uuid.uuid4()), user_id=user_id, trip_id=trip_id,
            booking_status='confirmed', pnr_number=pnr, booking_details={}
        )
        db_user.add(user)
        db_user.add(booking)
        
        # Add Mock Live Position: Train is at NDLS (Sequence 1)
        mock_live = TrainLiveUpdate(
            train_number=train_no, station_code='NDLS', sequence=1,
            is_current_station=True, recorded_at=datetime.utcnow()
        )
        db_transit.add(mock_live)
        db_user.commit()
        db_transit.commit()

        print(f"Test User: {user_id}, Train: {train_no} (Live at NDLS)")

        # 2. Test Sync (User at NDLS, Train at NDLS)
        print("\n[Test 1] Checking SYNCED Location (User & Train at NDLS)...")
        res_sync = await safety_service.check_journey_deviation(user_id, ndls.latitude, ndls.longitude, db_user)
        print(f"Result: {res_sync['status']}, Mode: {res_sync['mode']}, Dist: {res_sync['distance_km']}km")
        if res_sync['status'] == 'ok':
             print("[PASS] User correctly identified as synced with train.")
        else:
             print("[FAIL] User incorrectly flagged as deviated.")

        # 3. Test Desync (User at BCT, but Train still at NDLS)
        print("\n[Test 2] Checking DESYNCED Location (User at BCT, Train at NDLS)...")
        res_desync = await safety_service.check_journey_deviation(user_id, bct.latitude, bct.longitude, db_user)
        print(f"Result: {res_desync['status']}, Mode: {res_desync['mode']}, Dist: {res_desync['distance_km']}km")
        if res_desync['status'] == 'deviated' and res_desync['distance_km'] > 100:
            print("[PASS] Correctly detected deviation (User is too far ahead of train).")
        else:
            print("[FAIL] Failed to detect segment-based deviation.")

    finally:
        db_user.query(Booking).filter(Booking.user_id == user_id).delete()
        db_user.query(User).filter(User.id == user_id).delete()
        db_transit.query(TrainLiveUpdate).filter(TrainLiveUpdate.train_number == train_no).delete()
        db_user.commit()
        db_transit.commit()
        db_user.close()
        db_transit.close()

if __name__ == "__main__":
    asyncio.run(test_deviation_engine())
