import sqlite3
import os

db_path = 'backend/database/transit_graph.db'

def setup_availability_cache():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Ensuring train_availability_cache table exists (Task 2.6)...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS train_availability_cache (
            train_number TEXT,
            from_station TEXT,
            to_station TEXT,
            travel_date TEXT,
            quota TEXT,
            class_type TEXT,
            available_seats INTEGER,
            last_updated DATETIME,
            PRIMARY KEY (train_number, from_station, to_station, travel_date, quota, class_type)
        )
    """)
    
    # Also create index for fast lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_avail_cache_lookup ON train_availability_cache(train_number, travel_date)")
    
    conn.commit()
    conn.close()
    print("Availability cache table ready.")

if __name__ == "__main__":
    setup_availability_cache()
