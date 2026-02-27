import json
import os
import re
from sqlalchemy.orm import sessionmaker
from database import engine, Base
from database.models import StationMaster, Station, Stop

# Create tables
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Load data from JSON
# Using relative path for robustness
current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, "..", "..", "src", "data", "station_search_data.json")
# Fallback to hardcoded path if relative fails
if not os.path.exists(json_path):
    json_path = r"C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\src\data\station_search_data.json"

print(f"JSON path: {json_path}")
print(f"Exists: {os.path.exists(json_path)}")

if not os.path.exists(json_path):
    print("❌ STATION DATA NOT FOUND. SEARCH WILL REMAIN EMPTY.")
    db.close()
    exit(1)

with open(json_path, 'r') as f:
    data = json.load(f)

stations = data['stations']

print("Preparing bulk data for all station models...")
master_data = []
station_data = []
stop_data = []

for station in stations:
    is_junction = bool(re.search(r'JN|JUNCTION|TERMINUS|CENTRAL', station['name'], re.IGNORECASE))
    
    # StationMaster (Legacy)
    master_data.append({
        "station_code": station['code'],
        "station_name": station['name'],
        "city": station['city'],
        "state": station['state'],
        "is_junction": is_junction,
        "latitude": 0.0,
        "longitude": 0.0
    })
    
    # Station (Search)
    station_data.append({
        "code": station['code'],
        "name": station['name'],
        "city": station['city'],
        "latitude": 0.0,
        "longitude": 0.0
    })

    # Stop (GTFS/Routing Engine)
    stop_data.append({
        "stop_id": station['code'], # Use code as ID for easy lookup
        "name": station['name'],
        "city": station['city'],
        "state": station['state'],
        "latitude": 0.0,
        "longitude": 0.0,
        "is_major_junction": is_junction
    })

print(f"Bulk inserting {len(stations)} entries into each table...")
try:
    db.bulk_insert_mappings(StationMaster, master_data)
    db.bulk_insert_mappings(Station, station_data)
    db.bulk_insert_mappings(Stop, stop_data)
    db.commit()
    print(f"✅ Successfully seeded {len(stations)} stations across all models")
except Exception as e:
    db.rollback()
    print(f"❌ Error during bulk seed: {e}")
finally:
    db.close()
