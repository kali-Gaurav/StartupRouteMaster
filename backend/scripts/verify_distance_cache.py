import sqlite3
import sys
import os

def verify_distance_cache():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    try:
        # Get IDs for NDLS and DLI
        ndls_id = conn.execute("SELECT id FROM stops WHERE code='NDLS'").fetchone()[0]
        dli_id = conn.execute("SELECT id FROM stops WHERE code='DLI'").fetchone()[0]
        
        res = conn.execute("SELECT distance_km FROM distance_cache WHERE src_id=? AND dst_id=?", (ndls_id, dli_id)).fetchone()
        print(f"Distance NDLS -> DLI: {res[0] if res else 'None'} km")
        
        if res and res[0] < 5.0:
            print("🎉 SUCCESS: Distance cache is functional and accurate.")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_distance_cache()
