import sqlite3
import os

db_path = "backend/database/transit_graph.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print(f"Tables in {db_path}:")
table_names = [t[0] for t in tables]
for name in sorted(table_names):
    print(f"  - {name}")
conn.close()
