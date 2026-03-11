import sqlite3
import os

db_path = 'backend/database/transit_graph.db'

def to_seconds(t_str):
    if not t_str: return 0
    h, m, s = map(int, t_str.split(':'))
    return h * 3600 + m * 60 + s

def populate_timestamps():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Fetching stop_times for timestamp conversion...")
    cursor.execute("SELECT id, arrival_time, departure_time FROM stop_times")
    rows = cursor.fetchall()
    
    print(f"Updating {len(rows)} rows...")
    updates = []
    for row in rows:
        updates.append((to_seconds(row[1]), to_seconds(row[2]), row[0]))
        
        if len(updates) >= 10000:
            cursor.executemany("UPDATE stop_times SET arrival_timestamp = ?, departure_timestamp = ? WHERE id = ?", updates)
            updates = []
            
    if updates:
        cursor.executemany("UPDATE stop_times SET arrival_timestamp = ?, departure_timestamp = ? WHERE id = ?", updates)

    conn.commit()
    conn.close()
    print("Timestamp population complete!")

if __name__ == "__main__":
    populate_timestamps()
