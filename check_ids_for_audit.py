
import sqlite3
import os

db_path = "backend/database/transit_graph.db"
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
codes = ["NDLS", "MMCT", "MS", "MAS", "HWH", "SBC", "BPL", "RKMP"]
placeholders = ",".join(["'"+c+"'" for c in codes])
cursor.execute(f"SELECT id, code, name FROM stops WHERE code IN ({placeholders})")
for row in cursor.fetchall(): print(row)
conn.close()
