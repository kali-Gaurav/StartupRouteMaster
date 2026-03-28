
import sqlite3
import os

db_path = "backend/database/transit_graph.db"
if not os.path.exists(db_path):
    print("❌ DB not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get count before cleanup
cursor.execute("SELECT COUNT(*) FROM train_live_updates")
before = cursor.fetchone()[0]

# Cleanup mock data (I injected 5000 rows recently)
cursor.execute("DELETE FROM train_live_updates")
conn.commit()

# Verify
cursor.execute("SELECT COUNT(*) FROM train_live_updates")
after = cursor.fetchone()[0]

print(f"🧹 Database Cleaned.")
print(f"   - Rows Before: {before}")
print(f"   - Rows After: {after} (Should be 0 if only mock was there)")

conn.close()
