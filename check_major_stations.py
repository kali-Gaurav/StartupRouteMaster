
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, stop_id, code FROM stops WHERE code IN ('NDLS', 'BCT', 'MS', 'MAS', 'HWH', 'SBC', 'BPL', 'RKMP')")
for row in cursor.fetchall(): print(row)
conn.close()
