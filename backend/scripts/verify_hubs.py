import sqlite3
import json
import sys
import os

def verify_hubs():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    try:
        # Check NDLS -> CSMT
        res = conn.execute("SELECT trains_json FROM hub_transit_index WHERE src_hub='NDLS' AND dst_hub='CSMT'").fetchone()
        print(f"Backbone NDLS -> CSMT: {res[0] if res else 'None'}")
        
        # Check HWH -> MAS
        res2 = conn.execute("SELECT trains_json FROM hub_transit_index WHERE src_hub='HWH' AND dst_hub='MAS'").fetchone()
        print(f"Backbone HWH -> MAS: {res2[0] if res2 else 'None'}")
        
        if res or res2:
            print("🎉 SUCCESS: Hub-to-Hub backbone index is functional.")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_hubs()
