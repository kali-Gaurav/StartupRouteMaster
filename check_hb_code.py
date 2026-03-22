
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, stop_id, code, name FROM stops WHERE name LIKE '%HABIBGANJ%' OR name LIKE '%RANI KAMALAPATI%' OR code = 'RKMP' OR code = 'HBJ'")
for row in cursor.fetchall(): print(row)
conn.close()
