import sqlite3
import datetime
import os
import sys

def check_numpy():
    print("Checking numpy stability...")
    try:
        import numpy
        print("✅ numpy imported successfully.")
        return True
    except Exception as e:
        print(f"❌ numpy crash: {e}")
        return False

def check_db_dates():
    print("Checking GTFS calendar dates...")
    db_path = "backend/database/transit_graph.db"
    if not os.path.exists(db_path):
        print(f"❌ DB not found at {db_path}")
        return False
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(end_date) FROM calendar")
        max_date = cursor.fetchone()[0]
        print(f"✅ Max calendar end_date: {max_date}")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ DB check failed: {e}")
        return False

def check_stop_times_columns():
    print("Checking stop_times columns...")
    db_path = "backend/database/transit_graph.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(stop_times)")
        cols = [c[1] for c in cursor.fetchall()]
        has_ts = "departure_timestamp" in cols and "arrival_timestamp" in cols
        print(f"✅ stop_times has timestamps: {has_ts}")
        conn.close()
        return has_ts
    except Exception as e:
        print(f"❌ stop_times check failed: {e}")
        return False

if __name__ == "__main__":
    check_numpy()
    check_db_dates()
    check_stop_times_columns()
