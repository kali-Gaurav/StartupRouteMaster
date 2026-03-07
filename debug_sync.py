import sqlite3

def debug_sync():
    t_conn = sqlite3.connect('backend/database/transit_graph.db')
    s_conn = sqlite3.connect('backend/database/railway_data.db')
    
    t_cur = t_conn.cursor()
    s_cur = s_conn.cursor()
    
    t_cur.execute("SELECT trip_id FROM trips LIMIT 5")
    print("Trips in transit_graph (trip_id col):", [r[0] for r in t_cur.fetchall()])
    
    s_cur.execute("SELECT train_no FROM train_fares LIMIT 5")
    print("Train Nos in railway_data:", [r[0] for r in s_cur.fetchall()])
    
    s_cur.execute("SELECT availability FROM train_fares WHERE availability IS NOT NULL LIMIT 1")
    row = s_cur.fetchone()
    if row:
        print("Sample availability JSON:", row[0])
    
    t_conn.close()
    s_conn.close()

if __name__ == "__main__":
    debug_sync()
