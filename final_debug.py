import sqlite3

def final_debug():
    t_conn = sqlite3.connect('backend/database/transit_graph.db')
    s_conn = sqlite3.connect('backend/database/railway_data.db')
    
    t_cur = t_conn.cursor()
    s_cur = s_conn.cursor()
    
    t_cur.execute("SELECT trip_id FROM trips LIMIT 5")
    t_ids = [str(r[0]).strip() for r in t_cur.fetchall()]
    print("Trips in transit_graph:", t_ids)
    
    s_cur.execute("SELECT train_no FROM train_fares LIMIT 10")
    s_nos = [str(r[0]).strip() for r in s_cur.fetchall()]
    print("Train Nos in railway_data:", s_nos)
    
    # Check for any overlap
    t_cur.execute("SELECT trip_id FROM trips")
    all_t_ids = set(str(row[0]).strip() for row in t_cur.fetchall())
    
    s_cur.execute("SELECT DISTINCT train_no FROM train_fares")
    all_s_nos = set(str(row[0]).strip() for row in s_cur.fetchall())
    
    overlap = all_t_ids.intersection(all_s_nos)
    print(f"Overlap count: {len(overlap)}")
    if overlap:
        print(f"Sample overlap: {list(overlap)[:5]}")
    
    s_cur.execute("SELECT train_no, availability FROM train_fares WHERE availability IS NOT NULL LIMIT 1")
    row = s_cur.fetchone()
    if row:
        print(f"Train {row[0]} has availability: {row[1][:100]}...")

    t_conn.close()
    s_conn.close()

if __name__ == "__main__":
    final_debug()
