import sys
import os
import math
from typing import Dict

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import SessionLocal
from database.models import Segment, Fare, Trip, TrainMaster
from core.pricing.fare_calculator import calculate_fare, FARE_RATES

def populate_fares():
    session = SessionLocal()
    try:
        segments = session.query(Segment).all()
        print(f"Processing {len(segments)} segments...")
        
        # Clear existing fares for safety or update logic
        # session.query(Fare).delete()
        
        new_fares = []
        for segment in segments:
            if not segment.distance_km:
                # Approximate distance if missing using cost or other metrics
                # For now, if missing, skip or use a default
                continue
                
            # Check if train is superfast
            is_sf = False
            if segment.trip_id:
                trip = session.query(Trip).filter(Trip.id == segment.trip_id).first()
                if trip:
                    # Get train type from TrainMaster or other source
                    # Assuming we can find it via trip.trip_id (often contains train number)
                    train_no = trip.trip_id.split('_')[0] if isinstance(trip.trip_id, str) else str(trip.trip_id)
                    train = session.query(TrainMaster).filter(TrainMaster.train_number == train_no).first()
                    if train and train.type:
                        is_sf = any(x in train.type.upper() for x in ["SUPERFAST", "RAJ", "DUR", "SHATABDI"])
            
            for coach in FARE_RATES.keys():
                try:
                    fare_breakdown = calculate_fare(segment.distance_km, coach, is_superfast=is_sf)
                    
                    # Create Fare record
                    fare = Fare(
                        segment_id=segment.id,
                        trip_id=segment.trip_id,
                        class_type=coach,
                        amount=fare_breakdown["total_fare"]
                    )
                    new_fares.append(fare)
                except Exception as e:
                    # print(f"Error calculating fare for segment {segment.id}, coach {coach}: {e}")
                    pass
            
            # Bulk insert in chunks
            if len(new_fares) >= 1000:
                session.add_all(new_fares)
                session.commit()
                print(f"Inserted {len(new_fares)} fare records...")
                new_fares = []
                
        if new_fares:
            session.add_all(new_fares)
            session.commit()
            print(f"Inserted final {len(new_fares)} fare records.")
            
        print("Fare population complete!")
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    populate_fares()
