import sqlite3

def migrate():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Migrating seat_inventory table...")
    try:
        cursor.execute("ALTER TABLE seat_inventory ADD COLUMN trip_id INTEGER")
        print("Added trip_id column.")
    except Exception as e:
        print(f"trip_id column might already exist: {e}")

    try:
        cursor.execute("ALTER TABLE seat_inventory ADD COLUMN total_seats INTEGER DEFAULT 0")
        print("Added total_seats column.")
    except Exception as e:
        print(f"total_seats column might already exist: {e}")

    try:
        # Rename seats_available to available_seats if needed
        cursor.execute("PRAGMA table_info(seat_inventory)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'seats_available' in cols and 'available_seats' not in cols:
            cursor.execute("ALTER TABLE seat_inventory RENAME COLUMN seats_available TO available_seats")
            print("Renamed seats_available to available_seats.")
    except Exception as e:
        print(f"Rename failed or not needed: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
