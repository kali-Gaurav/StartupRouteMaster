import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("data_cleanup")

def cleanup_data():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    logger.info("Starting Data Pruning...")

    # 1. Delete Short Trips (< 2 stops)
    cur.execute("""
        DELETE FROM trips 
        WHERE id IN (
            SELECT trip_id FROM stop_times GROUP BY trip_id HAVING COUNT(*) < 2
        )
    """)
    pruned_trips = cur.rowcount
    logger.info(f"Pruned {pruned_trips} short trips.")

    # 2. Delete Orphan Segments (no matching trip)
    cur.execute("DELETE FROM segments WHERE trip_id NOT IN (SELECT id FROM trips)")
    pruned_segs = cur.rowcount
    logger.info(f"Pruned {pruned_segs} orphan segments.")

    # 3. Delete Orphan StopTimes
    cur.execute("DELETE FROM stop_times WHERE trip_id NOT IN (SELECT id FROM trips)")
    pruned_st = cur.rowcount
    logger.info(f"Pruned {pruned_st} orphan stop_times.")

    # 4. Handle Invalid Coordinates
    # Instead of deleting stops (which might break foreign keys), we can null them 
    # or just let GraphBuilder skip them. 
    # For now, let's keep them but ensure search handles it.
    
    conn.commit()
    conn.close()
    logger.info("Cleanup complete.")

if __name__ == "__main__":
    cleanup_data()
