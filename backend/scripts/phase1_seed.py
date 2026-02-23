from backend.database import SessionLocal
from backend.database.models import Stop, Trip, Route, Agency, Calendar, StopTime, CalendarDate
from datetime import datetime, date, time
import uuid

def seed_phase1():
    db = SessionLocal()
    try:
        # 1. Agency
        agency = Agency(
            agency_id="IR",
            name="Indian Railways",
            url="https://www.irctc.co.in",
            timezone="Asia/Kolkata"
        )
        db.add(agency)
        db.flush()

        # 2. Stops
        ndls = Stop(
            stop_id="NDLS",
            code="NDLS",
            name="New Delhi",
            city="New Delhi",
            state="Delhi",
            latitude=28.6143,
            longitude=77.2148,
            location_type=1,
            is_major_junction=True
        )
        mmct = Stop(
            stop_id="MMCT",
            code="MMCT",
            name="Mumbai Central",
            city="Mumbai",
            state="Maharashtra",
            latitude=18.9696,
            longitude=72.8193,
            location_type=1,
            is_major_junction=True
        )
        db.add_all([ndls, mmct])
        db.flush()

        # 3. Calendar
        cal = Calendar(
            service_id="DAILY",
            monday=True, tuesday=True, wednesday=True, thursday=True, friday=True, saturday=True, sunday=True,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31)
        )
        db.add(cal)
        db.flush()

        # 4. Route
        route = Route(
            route_id="R12951",
            agency_id=agency.id,
            short_name="12951",
            long_name="Mumbai Rajdhani",
            route_type=2 # Rail
        )
        db.add(route)
        db.flush()

        # 5. Trip
        trip = Trip(
            trip_id="T12951",
            route_id=route.id,
            service_id="DAILY",
            headsign="Mumbai Central",
            direction_id=0
        )
        db.add(trip)
        db.flush()

        # 6. StopTimes
        st1 = StopTime(
            trip_id=trip.id,
            stop_id=ndls.id,
            arrival_time=time(16, 30),
            departure_time=time(16, 55),
            stop_sequence=1
        )
        st2 = StopTime(
            trip_id=trip.id,
            stop_id=mmct.id,
            arrival_time=time(8, 30),
            departure_time=time(8, 30),
            stop_sequence=2
        )
        db.add_all([st1, st2])
        
        db.commit()
        print("Phase 1 Seed data created successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_phase1()
