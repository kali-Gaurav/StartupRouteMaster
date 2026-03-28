
import sqlite3
import os

dbs = ["backend/database/transit_graph.db", "backend/database/railway_data.db"]

for db in dbs:
    if not os.path.exists(db):
        print(f"❌ {db} not found")
        continue
    print(f"\n📁 Database: {db}")
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cursor.fetchall()}
    
    # 🔍 RCA Target Check
    for target in ["segments", "calendar", "stops", "trips", "hub_connectivity_index"]:
        if target in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {target}")
            print(f"✅ Table '{target}' found with {cursor.fetchone()[0]} rows.")
        else:
            print(f"❌ Table '{target}' NOT FOUND.")
