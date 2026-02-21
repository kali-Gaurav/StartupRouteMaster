import sqlite3
# Connect to the human-readable database source
conn = sqlite3.connect('backend/database/railway_data.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", tables)
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
    count = cursor.fetchone()[0]
    print(f"{table[0]}: {count}")
    if table[0] == 'stops' and count > 0:
        cursor.execute("SELECT stop_id, name FROM stops LIMIT 5")
        print("Sample Stops:", cursor.fetchall())
    if table[0] == 'stations_master' and count > 0:
        cursor.execute("SELECT station_code, station_name FROM stations_master LIMIT 5")
        print("Sample StationsMaster:", cursor.fetchall())
conn.close()
