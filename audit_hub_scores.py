
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
print("--- Hub Connectivity Audit ---")
cursor.execute("SELECT src_hub_id, count(*) FROM hub_connectivity_index GROUP BY src_hub_id ORDER BY count(*) DESC LIMIT 10")
for row in cursor.fetchall(): print(row)
conn.close()
