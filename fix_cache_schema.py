import sqlite3
import os

db_path = 'backend/database/transit_graph.db'

def fix_schema():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Adding UNIQUE index to train_availability_cache for UPSERT support...")
    try:
        # Create a unique index on the columns that define a unique availability record
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_avail_unique_lookup 
            ON train_availability_cache (train_number, from_station_code, to_station_code, journey_date, class_type, quota)
        """)
        
        # Also do it for the fares table if needed
        print("Checking fares table schema...")
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='fares'")
        fare_schema = cursor.fetchone()[0]
        if "UNIQUE" not in fare_schema and "PRIMARY KEY" not in fare_schema:
             cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_fares_unique_lookup 
                ON fares (trip_id, class_type)
            """)
            
        conn.commit()
        print("Schema fixed successfully.")
    except Exception as e:
        print(f"Error fixing schema: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_schema()
