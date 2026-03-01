
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Tables ---")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall()]
print(tables)

for table in tables:
    print(f"\n--- Schema for {table} ---")
    cursor.execute(f"PRAGMA table_info({table});")
    for col in cursor.fetchall():
        print(col)
    
    print(f"--- Sample from {table} ---")
    cursor.execute(f"SELECT * FROM {table} LIMIT 3;")
    for row in cursor.fetchall():
        print(row)

conn.close()
