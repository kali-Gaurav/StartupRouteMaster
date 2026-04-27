
import sqlite3
import os

db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Calendar rows:")
cursor.execute("SELECT * FROM calendar LIMIT 2")
for row in cursor.fetchall():
    print(row)

print("\nCalendarDates rows:")
cursor.execute("SELECT * FROM calendar_dates LIMIT 2")
for row in cursor.fetchall():
    print(row)

conn.close()
