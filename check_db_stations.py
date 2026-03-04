import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()
codes = ('NDLS', 'MMCT', 'HWH', 'SBC', 'MAS', 'BCT')
query = f"SELECT code, name FROM stops WHERE code IN {codes}"
c.execute(query)
results = c.fetchall()
print("Found in DB:", results)
conn.close()
