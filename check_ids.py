
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, stop_id, code, name FROM stops WHERE id IN (15, 59, 60, 78)")
for row in cursor.fetchall(): print(row)
conn.close()
