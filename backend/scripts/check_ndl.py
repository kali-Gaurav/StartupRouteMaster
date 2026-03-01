
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- NDL Check ---")
cursor.execute("SELECT code, name FROM stops WHERE code IN ('NDL', 'NDLS')")
print(cursor.fetchall())

conn.close()
