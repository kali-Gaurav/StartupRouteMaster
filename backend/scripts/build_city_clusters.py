import sqlite3
import json
import sys
import os
from collections import defaultdict
from math import radians, cos, sin, acos

# Ensure backend package is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.config import Config

def haversine(lat1, lon1, lat2, lon2):
    if not all([lat1, lon1, lat2, lon2]): return 9999.0
    try:
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        return 6371 * acos(min(1.0, cos(lat1) * cos(lat2) * cos(lon2 - lon1) + sin(lat1) * sin(lat2)))
    except: return 9999.0

def build_city_clusters():
    db_url = Config.GET_SQLALCHEMY_URL("transit", is_async=False)
    db_path = db_url.replace("sqlite:///", "")
    
    if "postgresql" in db_url:
        print("⚠️ Geographical clustering script currently supports SQLite only. Skipping for Postgres.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print(f"🚀 Building Geographical City Clusters from {db_path}...")
    
    try:
        # 1. Reset Table
        conn.execute("DROP TABLE IF EXISTS city_clusters")
        conn.execute("""
            CREATE TABLE city_clusters (
                city_name TEXT PRIMARY KEY,
                station_codes_json TEXT
            )
        """)
        
        # 2. Fetch all stations with coordinates
        # We only cluster stations that have valid coordinates
        stations = conn.execute("SELECT id, code, name, latitude, longitude FROM stops WHERE latitude != 0.0 AND latitude IS NOT NULL").fetchall()
        
        # 3. Geographical Grouping (Greedy Clustering)
        # We group stations that are within 10km of each other
        processed_ids = set()
        clusters = []
        
        # Sort so results are stable
        sorted_stations = sorted(stations, key=lambda x: x['code'])
        
        for i, s1 in enumerate(sorted_stations):
            if s1['id'] in processed_ids: continue
            
            # Start a new cluster with this station
            current_cluster = [s1]
            processed_ids.add(s1['id'])
            
            # Find all other stations within 10km
            for j in range(i + 1, len(sorted_stations)):
                s2 = sorted_stations[j]
                if s2['id'] in processed_ids: continue
                
                dist = haversine(s1['latitude'], s1['longitude'], s2['latitude'], s2['longitude'])
                if dist <= 10.0:
                    current_cluster.append(s2)
                    processed_ids.add(s2['id'])
            
            if len(current_cluster) > 1:
                clusters.append(current_cluster)
        
        # 4. Name and Save Clusters
        insert_data = []
        for cluster in clusters:
            # Name the cluster after the shortest station code (e.g., NDLS)
            primary = sorted(cluster, key=lambda x: len(x['code']))[0]
            cluster_name = primary['code']
            codes = [s['code'] for s in cluster]
            insert_data.append((cluster_name, json.dumps(codes)))
            
        conn.executemany("INSERT INTO city_clusters VALUES (?, ?)", insert_data)
        conn.commit()
        
        print(f"🎉 Successfully built {len(insert_data)} geographical clusters.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    build_city_clusters()
