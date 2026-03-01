import sqlite3
import psycopg2
import io
import time
import os

# Connection Strings
SQLITE_PATH = 'backend/database/transit_graph.db'
POSTGRES_URL = os.getenv("DATABASE_URL")
if not POSTGRES_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

def sync_segments():
    print("🚀 Syncing 139,000+ Segments from transit_graph.db to Railway...")
    start_time = time.time()
    
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLite file not found at {SQLITE_PATH}")
        return

    s_conn = sqlite3.connect(SQLITE_PATH)
    s_conn.row_factory = sqlite3.Row
    
    try:
        p_conn = psycopg2.connect(POSTGRES_URL)
        p_cur = p_conn.cursor()
    except Exception as e:
        print(f"❌ Failed to connect to Railway: {e}")
        return

    print("🧹 Cleaning and preparing Railway schema...")
    p_cur.execute("DROP TABLE IF EXISTS segments CASCADE;")
    p_cur.execute("""
        CREATE TABLE segments (
            id TEXT PRIMARY KEY,
            source_station_id TEXT,
            dest_station_id TEXT,
            vehicle_id TEXT,
            trip_id TEXT,
            transport_mode TEXT,
            departure_time TIME,
            arrival_time TIME,
            arrival_day_offset INTEGER,
            duration_minutes INTEGER,
            distance_km FLOAT,
            cost FLOAT,
            operating_days TEXT
        );
    """)

    print("📦 Reading segments from SQLite...")
    f = io.StringIO()
    count = 0
    cols = [
        'id', 'source_station_id', 'dest_station_id', 'vehicle_id', 
        'trip_id', 'transport_mode', 'departure_time', 'arrival_time', 
        'arrival_day_offset', 'duration_minutes', 'distance_km', 'cost', 'operating_days'
    ]
    for row in s_conn.execute("SELECT * FROM segments"):
        vals = [str(row[c]) if row[c] is not None else '' for c in cols]
        f.write("\t".join(vals) + "\n")
        count += 1
        if count % 50000 == 0:
            print(f"   Buffered {count} segments...")

    f.seek(0)
    try:
        print(f"📡 Streaming {count} segments to Railway via COPY...")
        p_cur.copy_from(f, 'segments')
        
        print("⚡ Creating indexes for search performance...")
        p_cur.execute("CREATE INDEX idx_segments_source ON segments (source_station_id);")
        p_cur.execute("CREATE INDEX idx_segments_dest ON segments (dest_station_id);")
        p_cur.execute("CREATE INDEX idx_segments_trip ON segments (trip_id);")
        
        p_conn.commit()
        print(f"✨ SUCCESS! Synced {count} segments in {time.time() - start_time:.2f}s")
    except Exception as e:
        print(f"❌ Error: {e}")
        p_conn.rollback()
    finally:
        s_conn.close()
        p_conn.close()

if __name__ == "__main__":
    sync_segments()
