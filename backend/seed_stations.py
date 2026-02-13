import json
import os
import re
from sqlalchemy.orm import sessionmaker
from database import engine, Base
from models import StationMaster

# Create tables
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Load data from JSON
json_path = r"C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\src\data\station_search_data.json"
print(f"JSON path: {json_path}")
print(f"Exists: {os.path.exists(json_path)}")
with open(json_path, 'r') as f:
    data = json.load(f)

stations = data['stations']

for station in stations:
    # Determine is_junction
    is_junction = bool(re.search(r'JN|JUNCTION|TERMINUS|CENTRAL', station['name'], re.IGNORECASE))

    db_station = StationMaster(
        station_code=station['code'],
        station_name=station['name'],
        city=station['city'],
        state=station['state'],
        is_junction=is_junction
    )
    db.add(db_station)

db.commit()
db.close()

print(f"Seeded {len(stations)} stations")