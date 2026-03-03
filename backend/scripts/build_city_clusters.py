import sqlite3
import json
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def build_city_clusters():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building City-Cluster Adjacency (Suggestion #6)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS city_clusters")
        conn.execute("""
            CREATE TABLE city_clusters (
                city_name TEXT PRIMARY KEY,
                station_codes_json TEXT
            )
        """)
        
        # 2. Extract clusters based on the 'city' column in stops
        # We also manually clean up major ones (Delhi, Mumbai, etc.)
        print("  Grouping stations by city...")
        rows = conn.execute("SELECT code, city, name FROM stops").fetchall()
        
        clusters = defaultdict(list)
        for r in rows:
            city = r['city'].strip().upper() if r['city'] else "UNKNOWN"
            # Normalize common city names
            if "DELHI" in city: city = "DELHI"
            if "MUMBAI" in city or "BOMBAY" in city: city = "MUMBAI"
            if "CHENNAI" in city or "MADRAS" in city: city = "CHENNAI"
            if "KOLKATA" in city or "CALCUTTA" in city: city = "KOLKATA"
            if "BANGALORE" in city or "BENGALURU" in city: city = "BANGALORE"
            
            clusters[city].append(r['code'])
            
        # 3. Filter clusters (only keep ones with multiple stations)
        filtered_clusters = {name: codes for name, codes in clusters.items() if len(codes) > 1 and name != "UNKNOWN"}
        
        insert_data = [(name, json.dumps(codes)) for name, codes in filtered_clusters.items()]
        conn.executemany("INSERT INTO city_clusters VALUES (?, ?)", insert_data)
        conn.commit()
        
        print(f"🎉 Successfully built {len(insert_data)} city clusters.")
        
        # Verification check
        delhi = conn.execute("SELECT station_codes_json FROM city_clusters WHERE city_name = 'DELHI'").fetchone()
        if delhi:
            print(f"  - DELHI Cluster: {delhi[0]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_city_clusters()
