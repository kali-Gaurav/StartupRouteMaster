
import sqlite3
db_path = "c:/Users/Gaurav Nagar/OneDrive/Desktop/startupV2/backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
print(cursor.fetchone()[0])
conn.close()
