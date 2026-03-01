
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Station Check ---")
cursor.execute("SELECT code, name FROM stops WHERE code IN ('MMCT', 'RAY', 'BCT')")
print(cursor.fetchall())

cursor.execute("SELECT code, name FROM stops WHERE name LIKE '%Mumbai%' LIMIT 5")
print(cursor.fetchall())

conn.close()
