import sqlite3
import json

db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\nSample row from hub_connectivity_index:")
cursor.execute("SELECT src_hub_id, dst_hub_id, trains_json FROM hub_connectivity_index LIMIT 1")
row = cursor.fetchone()
if row:
    print(f"SRC: {row[0]}, DST: {row[1]}")
    print(f"TRAINS: {row[2][:200]}...")
    try:
        data = json.loads(row[2])
        print(f"Decoded first train: {data[0]}")
    except Exception as e:
        print(f"JSON Error: {e}")
else:
    print("Table is empty!")

conn.close()
