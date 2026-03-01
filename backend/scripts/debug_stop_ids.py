
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, stop_id, name FROM stops WHERE id=111 OR stop_id='BCT' OR stop_id='NDLS' OR code='NDLS' OR code='BCT'")
print(cursor.fetchall())

conn.close()
