
import sqlite3
import os

db_path = "backend/database/transit_graph.db"
if not os.path.exists(db_path):
    print(f"❌ DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("📋 TABLE: trip_segments")
cursor.execute("SELECT sql FROM sqlite_master WHERE name='trip_segments'")
print(cursor.fetchone()[0])

print("\n📊 Segment Distribution (Top 10 Trips)")
cursor.execute("SELECT trip_id, COUNT(*) FROM trip_segments GROUP BY trip_id ORDER BY COUNT(*) DESC LIMIT 10")
for row in cursor.fetchall():
    print(f"Trip {row[0]}: {row[1]} segments")

print("\n🔍 Checking MAS -> SBC direct trip")
# Find a trip that hits both MAS and SBC
cursor.execute("""
    SELECT t1.trip_id, t1.stop_sequence as s1, t2.stop_sequence as s2
    FROM trip_segments t1
    JOIN trip_segments t2 ON t1.trip_id = t2.trip_id
    WHERE t1.from_stop_id = (SELECT id FROM stops WHERE code='MAS')
      AND t2.to_stop_id = (SELECT id FROM stops WHERE code='SBC')
    LIMIT 5
""")
rows = cursor.fetchall()
if rows:
    for r in rows:
        print(f"✅ Found path in Trip {r[0]} between sequence {r[1]} and {r[2]}")
else:
    print("❌ NO DIRECT PATH in trip_segments between MAS and SBC.")
