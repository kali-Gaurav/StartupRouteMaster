import sqlite3
import json
import math
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def build_intelligent_indices():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # 1. STATION NEIGHBORHOOD INDEX (Walking Transfers)
        print("🔨 Building Station Neighborhood Index (3km walking radius)...")
        stations = conn.execute("SELECT id, code, latitude, longitude FROM stops").fetchall()
        
        # Create table
        conn.execute("DROP TABLE IF EXISTS station_neighborhood_index")
        conn.execute("CREATE TABLE station_neighborhood_index (station_code TEXT PRIMARY KEY, neighbors_json TEXT)")
        
        neighbor_map = defaultdict(list)
        for i, s1 in enumerate(stations):
            if i % 1000 == 0: print(f"  Processed {i} stations...")
            for s2 in stations:
                if s1['code'] == s2['code']: continue
                
                dist = haversine(s1['latitude'], s1['longitude'], s2['latitude'], s2['longitude'])
                if dist <= 3.0: # 3km radius
                    neighbor_map[s1['code']].append({
                        "code": s2['code'],
                        "dist_km": round(dist, 2),
                        "walk_min": int(dist * 12) # ~5km/h
                    })
        
        # Insert in bulk
        insert_data = [(code, json.dumps(neighs)) for code, neighs in neighbor_map.items()]
        conn.executemany("INSERT INTO station_neighborhood_index VALUES (?, ?)", insert_data)
        
        # 2. TRAIN PROFILE INDEX (Consolidated Metadata)
        print("🔨 Building Train Profile Index (Class & Running Masks)...")
        conn.execute("DROP TABLE IF EXISTS train_profile_index")
        conn.execute("""
            CREATE TABLE train_profile_index (
                train_no TEXT PRIMARY KEY,
                name TEXT,
                running_mask INTEGER,
                classes_mask INTEGER
            )
        """)
        
        # Fetch from railway_data.db (source)
        source_conn = sqlite3.connect('backend/database/railway_data.db')
        source_conn.row_factory = sqlite3.Row
        
        # Class mapping
        class_map = {"SL": 1, "3A": 2, "2A": 4, "1A": 8, "CC": 16, "EC": 32, "2S": 64}
        
        trains = source_conn.execute("SELECT * FROM trains_master").fetchall()
        running_days = {r['train_no']: r for r in source_conn.execute("SELECT * FROM train_running_days").fetchall()}
        
        # Get classes per train from fares or coaches
        # Simplified for now: check fares table
        train_classes = defaultdict(int)
        fares = source_conn.execute("SELECT train_no, class_code FROM train_fares").fetchall()
        for f in fares:
            mask = class_map.get(f['class_code'], 0)
            train_classes[str(f['train_no'])] |= mask

        profiles = []
        for t in trains:
            t_no = str(t['train_no'])
            # Calc running mask
            mask = 0
            rd = running_days.get(t_no)
            if rd:
                days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
                for idx, day in enumerate(days):
                    if rd[day]: mask |= (1 << idx)
            
            profiles.append((t_no, t['train_name'], mask, train_classes.get(t_no, 0)))
            
        conn.executemany("INSERT INTO train_profile_index VALUES (?, ?, ?, ?)", profiles)
        source_conn.close()
        
        conn.commit()
        print("🚀 Intelligent Indices Built Successfully.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_intelligent_indices()
