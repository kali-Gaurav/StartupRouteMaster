
import sqlite3
import os

db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Calendar Date Range ---")
cursor.execute("SELECT MIN(start_date), MAX(end_date) FROM calendar")
row = cursor.fetchone()
print(f"Calendar: {row[0]} to {row[1]}")

print("\n--- Calendar Dates (Exceptions) Range ---")
cursor.execute("SELECT MIN(date), MAX(date) FROM calendar_dates")
row = cursor.fetchone()
print(f"Exceptions: {row[0]} to {row[1]}")

print("\n--- Sample Trips Count ---")
cursor.execute("SELECT count(*) FROM trips")
print(f"Total Trips: {cursor.fetchone()[0]}")

conn.close()
