import sqlite3

def fix_schema():
    conn = sqlite3.connect('backend/database/transit_graph.db')
    cursor = conn.cursor()
    try:
        # Check for transfers.walking_time_minutes
        cursor.execute("PRAGMA table_info(transfers)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'walking_time_minutes' not in cols:
            print("Adding walking_time_minutes to transfers...")
            cursor.execute("ALTER TABLE transfers ADD COLUMN walking_time_minutes INTEGER DEFAULT 5 NOT NULL")
        
        # Any other potential gaps?
        # Let's check gtfs_routes vs Route model (models.py says gtfs_routes is the table name for Route)
        
        conn.commit()
        print("Schema fix complete.")
    except Exception as e:
        print(f"Error fixing schema: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_schema()
