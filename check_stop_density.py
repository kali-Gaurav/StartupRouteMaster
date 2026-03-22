
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT count(*) FROM (SELECT stop_id FROM stop_times GROUP BY stop_id HAVING count(*) > 5)")
print(f"Stations with > 5 trips: {cursor.fetchone()[0]}")
cursor.execute("SELECT count(*) FROM (SELECT stop_id FROM stop_times GROUP BY stop_id)")
print(f"Total stations: {cursor.fetchone()[0]}")
conn.close()
