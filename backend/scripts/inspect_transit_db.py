import sqlite3
import os

db_path = "database/transit_graph.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [t[0] for t in cursor.fetchall()]
print(f"Tables: {tables}")

for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"- {table}: {count} rows")
    
    # Sample row
    cursor.execute(f"SELECT * FROM {table} LIMIT 1")
    sample = cursor.fetchone()
    print(f"  Sample: {sample}")

conn.close()
