import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
if not os.path.exists(db_path):
    db_path = 'database/transit_graph.db'
conn = sqlite3.connect(db_path)
res = conn.execute("SELECT id FROM stops WHERE code='NDLS'").fetchone()
if res:
    ndls_id = res[0]
    print(f"NDLS ID: {ndls_id}")
    count = conn.execute(f"SELECT count(*) FROM hub_connectivity_index WHERE src_hub_id={ndls_id} OR dst_hub_id={ndls_id}").fetchone()[0]
    print(f"Hub entries for NDLS: {count}")
    
    mmct_res = conn.execute("SELECT id FROM stops WHERE code='MMCT'").fetchone()
    if mmct_res:
        mmct_id = mmct_res[0]
        print(f"MMCT ID: {mmct_id}")
        count2 = conn.execute(f"SELECT count(*) FROM hub_connectivity_index WHERE (src_hub_id={ndls_id} AND dst_hub_id={mmct_id})").fetchone()[0]
        print(f"Direct Hub entries NDLS->MMCT: {count2}")
else:
    print("NDLS not found in stops table.")
conn.close()
