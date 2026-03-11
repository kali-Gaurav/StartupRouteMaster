import sqlite3
import os

db_path = 'backend/database/transit_graph.db'

def finalize_stops_and_search():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Updating data_quality_score (Task 1.11)...")
    # Rule: 
    # Starts at 100.
    # -50 if latitude/longitude is exactly 0.0 (though we checked this is not the case)
    # -20 if city is empty
    # -20 if state is empty
    # -10 if code is empty or "AA" (test data marker)
    
    cursor.execute("""
        UPDATE stops 
        SET data_quality_score = 100 - (
            (CASE WHEN latitude = 0.0 OR longitude = 0.0 THEN 50 ELSE 0 END) +
            (CASE WHEN city IS NULL OR city = '' THEN 20 ELSE 0 END) +
            (CASE WHEN state IS NULL OR state = '' THEN 20 ELSE 0 END) +
            (CASE WHEN code IS NULL OR code = '' OR code = 'AA' THEN 10 ELSE 0 END)
        )
    """)
    conn.commit()

    print("Building station_search_index (FTS5) (Task 1.12)...")
    # First, make sure the FTS table is clear or recreated
    try:
        cursor.execute("DROP TABLE IF EXISTS stops_fts")
        cursor.execute("CREATE VIRTUAL TABLE stops_fts USING fts5(code, name, city)")
    except Exception as e:
        print(f"FTS Re-creation Error (might be okay if it already exists): {e}")

    # Re-insert data into FTS index
    print("Populating FTS search index...")
    cursor.execute("INSERT INTO stops_fts(code, name, city) SELECT code, name, city FROM stops")

    conn.commit()
    conn.close()
    print("Station data quality (1.11) and Search Index (1.12) Complete!")

if __name__ == "__main__":
    finalize_stops_and_search()
