
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT max(id) FROM stops")
print(f"Max Stop ID: {cursor.fetchone()[0]}")
cursor.execute("SELECT count(*) FROM stops")
print(f"Total Stops: {cursor.fetchone()[0]}")
conn.close()
