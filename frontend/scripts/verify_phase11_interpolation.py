import sys
import os
from datetime import datetime, timedelta

# Adjust path to include the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from backend.services.realtime_ingestion.position_estimator import TrainPositionEstimator
from backend.database.models import TrainLiveUpdate, TrainStation, Stop

def setup_test_data(session):
    # 0. Cleanup Old
    train_no = "11001"
    session.query(Stop).filter(Stop.stop_id.in_(["STN_A", "STN_B"])).delete(synchronize_session=False)
    session.query(TrainStation).filter(TrainStation.train_number == train_no).delete(synchronize_session=False)
    session.query(TrainLiveUpdate).filter(TrainLiveUpdate.train_number == train_no).delete(synchronize_session=False)
    session.commit()

    # 1. Create two stops with coords
    stn_a = Stop(stop_id="STN_A", code="STN_A", name="Station A", latitude=10.0, longitude=70.0)
    stn_b = Stop(stop_id="STN_B", code="STN_B", name="Station B", latitude=11.0, longitude=71.0)
    session.add_all([stn_a, stn_b])
    
    # 2. Create Train Schedule
    train_no = "11001"
    sched_a = TrainStation(train_number=train_no, station_code="STN_A", station_name="Station A", sequence=1, distance_km=0)
    sched_b = TrainStation(train_number=train_no, station_code="STN_B", station_name="Station B", sequence=2, distance_km=100)
    session.add_all([sched_a, sched_b])
    
    # 3. Create Live Update (Train left Station A 30 mins ago)
    update = TrainLiveUpdate(
        train_number=train_no,
        station_code="STN_A",
        sequence=1,
        status="Departed",
        delay_minutes=15,
        recorded_at=datetime.utcnow() - timedelta(minutes=30)
    )
    session.add(update)
    session.commit()
    return train_no

def verify_interpolation():
    session = SessionLocal()
    try:
        train_no = setup_test_data(session)
        estimator = TrainPositionEstimator(session)
        
        # Act
        position = estimator.estimate_position(train_no)
        
        # Assert
        if not position:
            print("❌ Failure: No position returned.")
            return

        print(f"✅ Position Estimated: {position['lat']}, {position['lon']}")
        print(f"✅ Progress: {position['progress_percentage']}%")
        
        # Since it departed 30 mins ago and we estimate travel time as ~109 mins (100km / 55kmh * 60)
        # progress should be around 30/109 ~= 27.5%
        if 20 < position['progress_percentage'] < 40:
             print("✅ Mathematical Correctness: Progress is within expected bounds (~27%).")
        else:
             print(f"⚠️ Warning: Unusual progress percentage {position['progress_percentage']}%")

        if 'last_station' in position and 'next_station' in position:
             print("✅ Schema Correctness: Rich station data returned.")
        else:
             print("❌ Failure: Missing rich station data in response.")

    finally:
        session.close()

if __name__ == "__main__":
    verify_interpolation()
