#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding='utf-8')

from backend.database import Base, engine, SessionLocal
from backend.models import *
from backend.etl.sqlite_to_postgres import run_etl

print("Step 1: Creating all database tables...")
try:
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created!")
except Exception as e:
    print(f"Table creation note: {str(e)[:100]}")
    print("(Continuing anyway - tables may already exist)")

print("\nStep 2: Running ETL to import railway data...")
try:
    run_etl()
    print("✓ ETL completed!")
except Exception as e:
    print(f"ETL error: {str(e)[:200]}")

# Check data loaded
print("\nStep 3: Verifying data...")
s = SessionLocal()
try:
    from backend.models import Station, Vehicle, Segment
    stations = s.query(Station).count()
    vehicles = s.query(Vehicle).count()
    segments = s.query(Segment).count()
    print(f"Data loaded:")
    print(f"  Stations: {stations}")
    print(f"  Vehicles: {vehicles}")
    print(f"  Segments: {segments}")
except Exception as e:
    print(f"Check error: {e}")
finally:
    s.close()
