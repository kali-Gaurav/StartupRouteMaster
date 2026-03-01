#!/usr/bin/env python3
from backend.etl.sqlite_to_postgres import run_etl
from backend.database import SessionLocal
from backend.models import Station, Vehicle, Segment

print("Running ETL to import railway data from SQLite...")
try:
    run_etl()
    print("✅ ETL completed successfully!")
except Exception as e:
    print(f"⚠️  ETL error: {e}")

# Check data loaded
s = SessionLocal()
stations = s.query(Station).count()
vehicles = s.query(Vehicle).count()
segments = s.query(Segment).count()
print(f"\n📊 Data loaded into PostgreSQL:")
print(f"   Stations: {stations}")
print(f"   Vehicles: {vehicles}")
print(f"   Segments: {segments}")
s.close()
