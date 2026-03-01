import sqlite3
import os

db_path = os.path.join("backend", "database", "transit_graph.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT count(*) FROM stops WHERE is_major_junction = 1")
print(f"Junctions (1): {cursor.fetchone()[0]}")

cursor.execute("SELECT count(*) FROM stops WHERE is_major_junction = '1'")
print(f"Junctions ('1'): {cursor.fetchone()[0]}")

cursor.execute("SELECT count(*) FROM stops WHERE is_major_junction IS NOT NULL")
print(f"Non-null Junction field: {cursor.fetchone()[0]}")

conn.close()
