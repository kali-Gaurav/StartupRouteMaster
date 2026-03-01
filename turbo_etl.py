import sqlite3
import psycopg2
import json
import io
import time
import os

# Connection Strings
SQLITE_PATH = 'backend/database/railway_data.db'
POSTGRES_URL = os.getenv("DATABASE_URL")
if not POSTGRES_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

def get_day_mask(row):
    mask = 0
    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    for i, day in enumerate(days):
        try:
            val = row[day]
            if val == 1 or val == '1' or str(val).lower() == 'true':
                mask |= (1 << i)
        except:
            continue
    return mask

def run_turbo_etl():
    print("🚀 Starting ULTRA Turbo ETL (Object-Mapped Optimization)...")
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

    print("🧹 Preparing Railway schema...")
    p_cur.execute("DROP TABLE IF EXISTS station_transit_index CASCADE;")
    p_cur.execute("""
        CREATE TABLE station_transit_index (
            station_code TEXT PRIMARY KEY,
            station_name TEXT,
            trains_map JSONB -- format: {"train_no": [arr, dep, day_mask, seq], ...}
        );
    """)

    print("📅 Indexing train running schedules...")
    train_days = {}
    try:
        for row in s_conn.execute("SELECT * FROM train_running_days"):
            train_days[str(row['train_no'])] = get_day_mask(row)
    except Exception as e:
        print(f"⚠️ Warning: {e}")

    print("📦 Building station object maps...")
    station_data = {} 
    query = """
        SELECT tr.train_no, tr.station_code, sm.station_name, 
               tr.arrival_time, tr.departure_time, tr.seq_no 
        FROM train_routes tr
        LEFT JOIN stations_master sm ON tr.station_code = sm.station_code
    """
    count = 0
    for row in s_conn.execute(query):
        code = str(row['station_code'])
        if code not in station_data:
            station_data[code] = {'name': row['station_name'] or code, 'trains': {}}
        
        station_data[code]['trains'][str(row['train_no'])] = [
            row['arrival_time'],
            row['departure_time'],
            train_days.get(str(row['train_no']), 127),
            row['seq_no']
        ]
        count += 1

    print(f"📡 Streaming {len(station_data)} stations to Railway...")
    f = io.StringIO()
    for code, data in station_data.items():
        clean_name = str(data['name']).replace('\t', ' ').replace('\n', ' ')
        json_data = json.dumps(data['trains'])
        f.write(f"{code}\t{clean_name}\t{json_data}\n")
    
    f.seek(0)
    try:
        p_cur.copy_from(f, 'station_transit_index', columns=('station_code', 'station_name', 'trains_map'))
        print("⚡ Creating GIN index on keys (train_no) for O(1) intersection...")
        p_cur.execute("CREATE INDEX idx_station_trains_gin ON station_transit_index USING GIN (trains_map);")
        p_conn.commit()
        print(f"✨ SUCCESS! Synced in {time.time() - start_time:.2f}s")
    except Exception as e:
        print(f"❌ Error: {e}")
        p_conn.rollback()
    finally:
        s_conn.close()
        p_conn.close()

if __name__ == "__main__":
    run_turbo_etl()
