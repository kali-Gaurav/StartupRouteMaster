import sqlite3
import math
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def build_distance_cache():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Haversine Distance Cache (Suggestion #9)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS distance_cache")
        conn.execute("""
            CREATE TABLE distance_cache (
                src_id INTEGER,
                dst_id INTEGER,
                distance_km REAL,
                PRIMARY KEY (src_id, dst_id)
            )
        """)
        
        # 2. Fetch all stations
        stations = conn.execute("SELECT id, latitude, longitude FROM stops").fetchall()
        
        print(f"  Calculating proximity for {len(stations)} stations (10km radius)...")
        cache_data = []
        for i, s1 in enumerate(stations):
            if i % 1000 == 0: print(f"    Processed {i} stations...")
            for s2 in stations:
                if s1['id'] == s2['id']: continue
                
                # Fast bounding box check before heavy trig
                # 1 degree lat is approx 111km. 10km is ~0.09 degrees
                if abs(s1['latitude'] - s2['latitude']) > 0.1: continue
                if abs(s1['longitude'] - s2['longitude']) > 0.1: continue
                
                dist = haversine(s1['latitude'], s1['longitude'], s2['latitude'], s2['longitude'])
                if dist <= 10.0:
                    cache_data.append((s1['id'], s2['id'], round(dist, 3)))
                    
        # 3. Bulk Insert
        print(f"  Inserting {len(cache_data)} proximity pairs into cache...")
        conn.executemany("INSERT INTO distance_cache VALUES (?, ?, ?)", cache_data)
        conn.commit()
        print("🎉 Successfully built distance cache.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_distance_cache()
