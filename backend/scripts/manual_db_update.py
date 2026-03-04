import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 1. Get NDLS ID
c.execute("SELECT id FROM stops WHERE code='NDLS'")
res = c.fetchone()
if res:
    ndls_id = res[0]
    print(f"Found NDLS with ID: {ndls_id}")
    
    # 2. Insert/Update facilities
    import uuid
    c.execute("DELETE FROM station_facilities WHERE stop_id=?", (ndls_id,))
    c.execute("""
        INSERT INTO station_facilities (id, stop_id, has_ambulance, medical_contact, medical_rank)
        VALUES (?, ?, 1, '+91-11-23340000', 5)
    """, (str(uuid.uuid4()), ndls_id))
    conn.commit()
    print("Successfully updated station_facilities for NDLS.")
else:
    print("NDLS not found in stops table.")

conn.close()
