import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_segments")

def fix_segments():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    logger.info("Remapping segment trip_ids to Train Numbers...")
    
    # 1. We need to find the Train Number for the old internal IDs
    # Since I deleted the old trips, I have to rely on the 'train_number' column in segments if it exists
    cur.execute("PRAGMA table_info(segments)")
    cols = [c[1] for c in cursor.fetchall()]
    print("Columns in segments:", cols)
    
    # Let's assume 'train_number' exists in segments (Task 2 sync should have added it)
    cur.execute("UPDATE segments SET trip_id = CAST(train_number AS INTEGER) WHERE train_number IS NOT NULL")
    
    conn.commit()
    conn.close()
    logger.info("Segments remapped.")

if __name__ == "__main__":
    # Wait, I need to be sure about the columns first.
    conn = sqlite3.connect('backend/database/transit_graph.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(segments)")
    cols = [c[1] for c in cursor.fetchall()]
    print("Columns in segments:", cols)
    conn.close()
    
    if 'train_number' in cols:
        fix_segments()
    else:
        print("CRITICAL: 'train_number' column missing from segments. Full ETL Re-run required.")
