"""
Supabase Database Setup - Create tables from models.
Run this script to initialize the database schema.
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from sqlalchemy import create_engine, text
from database.infrastructure.base import Base
from config import get_bootstrap_settings


def create_tables():
    """Create all tables in the database."""
    settings = get_bootstrap_settings()
    
    # Create engine
    engine = create_engine(settings.database_url)
    
    # Create tables
    Base.metadata.create_all(engine)
    
    print("✅ All tables created successfully!")
    
    # Print table list
    with engine.connect() as conn:
        result = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        tables = [row[0] for row in result.fetchall()]
        print(f"\n📋 Created tables:")
        for table in tables:
            print(f"  - {table}")


def seed_sample_data():
    """Seed sample data for testing."""
    settings = get_bootstrap_settings()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Sample routes
        routes = [
            {
                "id": "route-001",
                "train_number": "12951",
                "train_name": "Mumbai Rajdhani",
                "source_code": "NDLS",
                "source_name": "New Delhi",
                "dest_code": "BCT",
                "dest_name": "Mumbai Central",
                "departure_time": "16:55:00",
                "arrival_time": "08:35:00",
                "duration_minutes": 940,
                "days_of_operation": "1234567",
                "base_fare": 1200.0
            },
            {
                "id": "route-002",
                "train_number": "12909",
                "train_name": "Garib Rath",
                "source_code": "NDLS",
                "source_name": "New Delhi",
                "dest_code": "BCT",
                "dest_name": "Mumbai Central",
                "departure_time": "18:40:00",
                "arrival_time": "10:25:00",
                "duration_minutes": 945,
                "days_of_operation": "1234567",
                "base_fare": 850.0
            },
            {
                "id": "route-003",
                "train_number": "19019",
                "train_name": "Kota Exp",
                "source_code": "NDLS",
                "source_name": "New Delhi",
                "dest_code": "BCT",
                "dest_name": "Mumbai Central",
                "departure_time": "14:10:00",
                "arrival_time": "07:00:00",
                "duration_minutes": 1010,
                "days_of_operation": "1234567",
                "base_fare": 650.0
            }
        ]
        
        for route in routes:
            conn.execute(text("""
                INSERT INTO routes (id, train_number, train_name, source_code, source_name, 
                                   dest_code, dest_name, departure_time, arrival_time, 
                                   duration_minutes, days_of_operation, base_fare)
                VALUES (:id, :train_number, :train_name, :source_code, :source_name,
                        :dest_code, :dest_name, :departure_time, :arrival_time,
                        :duration_minutes, :days_of_operation, :base_fare)
                ON CONFLICT (id) DO NOTHING
            """), route)
        
        # Sample seat inventory
        inventory = [
            {
                "id": "inv-001",
                "train_number": "12951",
                "from_station_code": "NDLS",
                "to_station_code": "BCT",
                "journey_date": "2025-06-15",
                "class_type": "SL",
                "quota": "GN",
                "total_seats": 24,
                "available_seats": 18,
                "waitlist_count": 5,
                "status_text": "AVAILABLE"
            },
            {
                "id": "inv-002",
                "train_number": "12951",
                "from_station_code": "NDLS",
                "to_station_code": "BCT",
                "journey_date": "2025-06-15",
                "class_type": "3A",
                "quota": "GN",
                "total_seats": 64,
                "available_seats": 45,
                "waitlist_count": 0,
                "status_text": "AVAILABLE"
            }
        ]
        
        for inv in inventory:
            conn.execute(text("""
                INSERT INTO seat_inventory (id, train_number, from_station_code, to_station_code,
                                           journey_date, class_type, quota, total_seats,
                                           available_seats, waitlist_count, status_text)
                VALUES (:id, :train_number, :from_station_code, :to_station_code,
                        :journey_date, :class_type, :quota, :total_seats,
                        :available_seats, :waitlist_count, :status_text)
                ON CONFLICT (id) DO NOTHING
            """), inv)
        
        conn.commit()
        print("✅ Sample data seeded successfully!")


if __name__ == "__main__":
    create_tables()
    seed_sample_data()