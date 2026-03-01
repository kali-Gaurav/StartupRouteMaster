import sqlite3
import os

db_path = os.path.join('backend', 'database', 'railway_data.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables = ['train_routes', 'train_schedule', 'stop_times', 'segments', 'trains_master']
for t in tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        print(f"Table {t}: {count} rows")
        if count > 0:
            cursor.execute(f"SELECT * FROM {t} LIMIT 1")
            cols = [d[0] for d in cursor.description]
            row = cursor.fetchone()
            print(f"  Columns: {cols}")
            print(f"  Sample: {row}")
    except Exception as e:
        print(f"Table {t} error: {e}")

conn.close()
