import sqlite3
import json
import sys
import os

def verify_clusters():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    try:
        # Find city for NDLS
        res = conn.execute("SELECT city_name, station_codes_json FROM city_clusters WHERE station_codes_json LIKE '%NDLS%'").fetchone()
        if res:
            print(f"📊 NDLS City Mapping: {res[0]}")
            codes = json.loads(res[1])
            print(f"  - Neighboring Stations in Delhi Cluster: {codes[:5]}... (Total {len(codes)})")
            
            if len(codes) > 1:
                print("🎉 SUCCESS: City-Cluster adjacency functional.")
        else:
            print("❌ NDLS not found in any cluster")
            
    finally:
        conn.close()

if __name__ == "__main__":
    verify_clusters()
