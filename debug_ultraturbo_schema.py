
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
print("--- Table Info: calendar_dates ---")
cursor.execute("PRAGMA table_info('calendar_dates')")
for row in cursor.fetchall(): print(row)
print("\n--- Count: calendar_dates ---")
cursor.execute("SELECT count(*) FROM calendar_dates")
print(cursor.fetchone()[0])
conn.close()
