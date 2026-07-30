import sqlite3
db_paths = ["backend/database/transit_graph.db", "backend/database/railway_data.db"]
for db_path in db_paths:
    print(f"--- {db_path} ---")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM trips WHERE id = 19019").fetchone()
        if row: 
            print(dict(row))
        else:
            # Maybe it's trip_id column?
            row = conn.execute("SELECT * FROM trips WHERE trip_id = '19019'").fetchone()
            if row: print(dict(row))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
