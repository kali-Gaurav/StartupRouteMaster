import sqlite3

def check_stops(db_path):
    conn = sqlite3.connect(db_path)
    res = conn.execute("SELECT id, code FROM stops WHERE code IN ('NDLS', 'BCT', 'MMCT')").fetchall()
    print(f"Stops in {db_path}: {res}")
    
    # Also check if any trips exist for these stops
    if res:
        stop_ids = [r[0] for r in res]
        q = f"SELECT count(*) FROM stop_times WHERE stop_id IN ({','.join(['?']*len(stop_ids))})"
        count = conn.execute(q, stop_ids).fetchone()[0]
        print(f"Stop times for these stops: {count}")
        
    conn.close()

if __name__ == "__main__":
    check_stops('backend/database/transit_graph.db')
    check_stops('backend/database/railway_data.db')
