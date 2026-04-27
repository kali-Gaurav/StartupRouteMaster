
import sqlite3
db_path = "c:/Users/Gaurav Nagar/OneDrive/Desktop/startupV2/backend/data/transit.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cursor.fetchall())
conn.close()
