import sqlite3
import json
import sys
import os

# Ensure backend package is importable
sys.path.append(os.getcwd())

def build_hot_stations():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Station Hot-Load Index (Suggestion #18)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS station_hot_departures")
        conn.execute("""
            CREATE TABLE station_hot_departures (
                station_id INTEGER PRIMARY KEY,
                departures_json TEXT
            )
        """)
        
        # 2. Get Top 100 stations by rank
        print("  Identifying top 100 hot stations...")
        top_stations = conn.execute("""
            SELECT station_id FROM station_rank 
            ORDER BY connectivity_score DESC LIMIT 100
        """).fetchall()
        top_ids = [r[0] for r in top_stations]
        
        # 3. Extract departures for these stations
        print(f"  Hot-loading departures for {len(top_ids)} stations...")
        insert_data = []
        for sid in top_ids:
            deps = conn.execute("""
                SELECT trip_id, departure_time 
                FROM stop_times WHERE stop_id = ?
            """, (sid,)).fetchall()
            
            dep_list = [{"t": r['trip_id'], "d": r['departure_time']} for r in deps]
            insert_data.append((sid, json.dumps(dep_list)))
            
        conn.executemany("INSERT INTO station_hot_departures VALUES (?, ?)", insert_data)
        conn.commit()
        print("🎉 Successfully populated hot-load index for top 100 stations.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_hot_stations()
