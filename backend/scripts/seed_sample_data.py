"""
Sample Data Seeder for Demo
Creates realistic train routes, schedules, and availability data for investor presentation.
"""

import sys
from pathlib import Path
from datetime import date, datetime, time, timedelta
from typing import List, Dict, Any

# Add backend to path
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from database.session import get_db
from database.models import (
    Route, Stop, Schedule, Train, Station,
    SeatInventory, User, Booking
)
import uuid


# Popular routes for demo
SAMPLE_ROUTES = [
    {
        "train_no": "12951",
        "train_name": "Mumbai Rajdhani",
        "from_code": "NDLS",
        "from_name": "New Delhi",
        "to_code": "BCT",
        "to_name": "Mumbai Central",
        "duration_minutes": 960,
        "classes": ["1A", "2A", "3A"],
        "departure_time": time(16, 55),
        "arrival_time": time(8, 35),
        "base_fares": {"1A": 3500, "2A": 2500, "3A": 1500}
    },
    {
        "train_no": "12909",
        "train_name": "Garib Rath",
        "from_code": "NDLS",
        "from_name": "New Delhi",
        "to_code": "BCT",
        "to_name": "Mumbai Central",
        "duration_minutes": 975,
        "classes": ["3A", "CC"],
        "departure_time": time(18, 40),
        "arrival_time": time(10, 25),
        "base_fares": {"3A": 1100, "CC": 850}
    },
    {
        "train_no": "19019",
        "train_name": "Kota Exp",
        "from_code": "NDLS",
        "from_name": "New Delhi",
        "to_code": "BCT",
        "to_name": "Mumbai Central",
        "duration_minutes": 1010,
        "classes": ["SL", "3A", "2A"],
        "departure_time": time(14, 10),
        "arrival_time": time(7, 0),
        "base_fares": {"SL": 500, "3A": 1300, "2A": 2100}
    },
    {
        "train_no": "12615",
        "train_name": "Grand Trunk Exp",
        "from_code": "NDLS",
        "from_name": "New Delhi",
        "to_code": "MAS",
        "to_name": "Chennai Central",
        "duration_minutes": 2100,
        "classes": ["1A", "2A", "3A", "SL"],
        "departure_time": time(19, 15),
        "arrival_time": time(10, 45),
        "base_fares": {"1A": 5500, "2A": 4000, "3A": 2500, "SL": 900}
    },
    {
        "train_no": "12301",
        "train_name": "Howrah Rajdhani",
        "from_code": "NDLS",
        "from_name": "New Delhi",
        "to_code": "HWH",
        "to_name": "Howrah Jn",
        "duration_minutes": 1380,
        "classes": ["1A", "2A", "3A"],
        "departure_time": time(16, 55),
        "arrival_time": time(9, 55),
        "base_fares": {"1A": 4500, "2A": 3200, "3A": 2000}
    },
    {
        "train_no": "12722",
        "train_name": "Nizamuddin Exp",
        "from_code": "NZM",
        "from_name": "Delhi Sarai Rohilla",
        "to_code": "SC",
        "to_name": "Secunderabad",
        "duration_minutes": 1500,
        "classes": ["2A", "3A", "SL"],
        "departure_time": time(7, 15),
        "arrival_time": time(12, 15),
        "base_fares": {"2A": 2800, "3A": 1800, "SL": 700}
    },
    {
        "train_no": "12449",
        "train_name": "Samprk Kranti",
        "from_code": "NDLS",
        "from_name": "New Delhi",
        "to_code": "GKP",
        "to_name": "Gorakhpur",
        "duration_minutes": 840,
        "classes": ["2A", "3A", "SL"],
        "departure_time": time(21, 30),
        "arrival_time": time(9, 30),
        "base_fares": {"2A": 1800, "3A": 1200, "SL": 500}
    },
    {
        "train_no": "12553",
        "train_name": "Saharanpur Exp",
        "from_code": "NDLS",
        "from_name": "New Delhi",
        "to_code": "LKO",
        "to_name": "Lucknow",
        "duration_minutes": 480,
        "classes": ["2A", "3A", "SL"],
        "departure_time": time(6, 0),
        "arrival_time": time(14, 0),
        "base_fares": {"2A": 1200, "3A": 800, "SL": 400}
    },
]

# Hub stations for transfer routes
HUB_STATIONS = [
    {"code": "NDLS", "name": "New Delhi", "connections": 150},
    {"code": "BCT", "name": "Mumbai Central", "connections": 120},
    {"code": "MAS", "name": "Chennai Central", "connections": 100},
    {"code": "HWH", "name": "Howrah Jn", "connections": 110},
    {"code": "SC", "name": "Secunderabad", "connections": 90},
    {"code": "LKO", "name": "Lucknow", "connections": 80},
    {"code": "JP", "name": "Jaipur", "connections": 70},
    {"code": "DHN", "name": "Dhanbad", "connections": 60},
    {"code": "GKP", "name": "Gorakhpur", "connections": 50},
    {"code": "PNBE", "name": "Patna", "connections": 55},
]


def seed_stations(db):
    """Seed station data."""
    print("🌍 Seeding stations...")
    
    for station in HUB_STATIONS:
        # Check if exists
        existing = db.query(Station).filter(
            Station.code == station["code"]
        ).first()
        
        if not existing:
            s = Station(
                id=str(uuid.uuid4()),
                code=station["code"],
                name=station["name"],
                zone="NR",  # Default zone
                state="India",
                latitude=28.6 + (hash(station["code"]) % 10) * 0.1,
                longitude=77.2 + (hash(station["code"]) % 10) * 0.1,
                connectivity_score=station["connections"] / 150 * 100
            )
            db.add(s)
            print(f"  ✅ Added station: {station['code']}")
        else:
            print(f"  ⏭️  Station exists: {station['code']}")
    
    db.commit()


def seed_routes(db):
    """Seed route data."""
    print("🚂 Seeding routes...")
    
    for route_data in SAMPLE_ROUTES:
        # Check if exists
        existing = db.query(Route).filter(
            Route.train_number == route_data["train_no"],
            Route.source_code == route_data["from_code"],
            Route.dest_code == route_data["to_code"]
        ).first()
        
        if not existing:
            route = Route(
                id=str(uuid.uuid4()),
                train_number=route_data["train_no"],
                train_name=route_data["train_name"],
                source_code=route_data["from_code"],
                source_name=route_data["from_name"],
                dest_code=route_data["to_code"],
                dest_name=route_data["to_name"],
                duration_minutes=route_data["duration_minutes"],
                classes_available=",".join(route_data["classes"]),
                base_fare=min(route_data["base_fares"].values())
            )
            db.add(route)
            print(f"  ✅ Added route: {route_data['train_no']} ({route_data['from_code']} → {route_data['to_code']})")
        else:
            print(f"  ⏭️  Route exists: {route_data['train_no']}")
    
    db.commit()


def seed_schedules(db, days_ahead: int = 30):
    """Seed schedules for the next N days."""
    print(f"📅 Seeding schedules (next {days_ahead} days)...")
    
    routes = db.query(Route).all()
    today = date.today()
    
    for route in routes:
        classes = route.classes_available.split(",")
        
        for day_offset in range(days_ahead):
            travel_date = today + timedelta(days=day_offset)
            
            # Check if schedule exists
            existing = db.query(Schedule).filter(
                Schedule.route_id == route.id,
                Schedule.travel_date == travel_date
            ).first()
            
            if not existing:
                # Determine availability based on demand
                # Higher demand for weekends and holidays
                is_weekend = travel_date.weekday() >= 5
                demand_factor = 1.3 if is_weekend else 1.0
                
                # Random availability
                import random
                if random.random() < 0.7 * demand_factor:
                    availability = "AVAILABLE"
                elif random.random() < 0.9:
                    availability = "LIMITED"
                else:
                    availability = "WAITLIST"
                
                schedule = Schedule(
                    id=str(uuid.uuid4()),
                    route_id=route.id,
                    train_number=route.train_number,
                    travel_date=travel_date,
                    departure_time=time(12, 0),  # Default
                    arrival_time=time(12, 0),
                    duration_minutes=route.duration_minutes,
                    base_fare=route.base_fare,
                    availability_status=availability,
                    total_seats=100,
                    available_seats=random.randint(0, 100) if availability != "SOLD OUT" else 0
                )
                db.add(schedule)
        
        if day_offset % 5 == 0:
            db.commit()
    
    db.commit()
    print(f"  ✅ Seeded schedules for {len(routes)} routes")


def seed_seat_inventory(db, days_ahead: int = 7):
    """Seed seat inventory for next N days."""
    print(f"💺 Seeding seat inventory (next {days_ahead} days)...")
    
    routes = db.query(Route).all()
    today = date.today()
    
    for route in routes:
        classes = route.classes_available.split(",")
        
        for day_offset in range(days_ahead):
            travel_date = today + timedelta(days=day_offset)
            
            for class_type in classes:
                # Check if exists
                existing = db.query(SeatInventory).filter(
                    SeatInventory.train_number == route.train_number,
                    SeatInventory.journey_date == travel_date,
                    SeatInventory.class_type == class_type
                ).first()
                
                if not existing:
                    import random
                    available = random.randint(0, 24)
                    
                    inventory = SeatInventory(
                        id=f"{route.train_number}:{route.source_code}:{route.dest_code}:{travel_date}:{class_type}",
                        train_number=route.train_number,
                        from_station_code=route.source_code,
                        to_station_code=route.dest_code,
                        journey_date=travel_date,
                        class_type=class_type,
                        quota="GN",
                        total_seats=24,
                        available_seats=available,
                        waitlist_count=random.randint(0, 10) if available == 0 else 0,
                        status_text="AVAILABLE" if available > 5 else ("LIMITED" if available > 0 else "SOLD OUT")
                    )
                    db.add(inventory)
    
    db.commit()
    print(f"  ✅ Seeded seat inventory")


def seed_demo_user(db):
    """Seed a demo user."""
    print("👤 Seeding demo user...")
    
    existing = db.query(User).filter(
        User.phone == "+919999999999"
    ).first()
    
    if not existing:
        user = User(
            id=str(uuid.uuid4()),
            phone="+919999999999",
            email="demo@routemaster.in",
            name="Demo User",
            created_at=datetime.now()
        )
        db.add(user)
        db.commit()
        print("  ✅ Added demo user: +919999999999")
    else:
        print("  ⏭️  Demo user exists")


def seed_sample_bookings(db):
    """Seed some sample bookings for demo."""
    print("🎫 Seeding sample bookings...")
    
    routes = db.query(Route).limit(3).all()
    today = date.today()
    
    for i, route in enumerate(routes):
        existing = db.query(Booking).filter(
            Booking.pnr_number == f"DEMO{i+1}001"
        ).first()
        
        if not existing:
            import random
            booking = Booking(
                id=str(uuid.uuid4()),
                pnr_number=f"DEMO{i+1}001",
                user_id="demo-user-id",
                journey_id=route.id,
                travel_date=today + timedelta(days=random.randint(1, 7)),
                train_number=route.train_number,
                from_station_code=route.source_code,
                to_station_code=route.dest_code,
                class_type=route.classes_available.split(",")[0],
                booking_status="confirmed",
                total_amount=route.base_fare * 1.1,
                amount_paid=route.base_fare * 1.1,
                seats_allocated=[f"{route.train_number}-{route.classes_available.split(',')[0]}-1"],
                created_at=datetime.now(),
                payment_completed_at=datetime.now()
            )
            db.add(booking)
            print(f"  ✅ Added sample booking: {booking.pnr_number}")
    
    db.commit()


def run_seed():
    """Run all seeding operations."""
    print("🚀 Starting Sample Data Seeding...")
    print("=" * 50)
    
    db = next(get_db())
    
    try:
        seed_stations(db)
        seed_routes(db)
        seed_schedules(db, days_ahead=30)
        seed_seat_inventory(db, days_ahead=7)
        seed_demo_user(db)
        seed_sample_bookings(db)
        
        print("=" * 50)
        print("✅ Sample data seeding complete!")
        print("\nDemo Data Summary:")
        print(f"  - Stations: {len(HUB_STATIONS)}")
        print(f"  - Routes: {len(SAMPLE_ROUTES)}")
        print(f"  - Schedules: 30 days × {len(SAMPLE_ROUTES)} routes")
        print(f"  - Seat Inventory: 7 days × {len(SAMPLE_ROUTES)} routes × ~3 classes")
        print(f"  - Demo User: +919999999999")
        print(f"  - Sample Bookings: 3")
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()