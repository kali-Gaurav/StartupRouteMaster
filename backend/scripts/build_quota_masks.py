import sqlite3
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def build_quota_masks():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    
    print("🚀 Building Quota Availability Bitmasks (Suggestion #2)...")
    
    try:
        # 1. Create the table
        conn.execute("DROP TABLE IF EXISTS train_quota_masks")
        conn.execute("""
            CREATE TABLE train_quota_masks (
                train_no TEXT,
                date TEXT,
                quota_mask INTEGER,
                PRIMARY KEY (train_no, date)
            )
        """)
        
        # 2. Get Trip -> Train mapping from transit_graph
        trip_to_train = {r[0]: r[1] for r in conn.execute("SELECT id, trip_id FROM trips").fetchall()}
        
        # 3. Quota Mapping
        QUOTA_MAP = {
            "GN": 1, "GENERAL": 1,
            "TQ": 2, "TATKAL": 2,
            "LD": 4, "LADIES": 4,
            "SS": 8, "SENIOR_CITIZEN": 8
        }
        
        # 4. Fetch from source
        source_conn = sqlite3.connect('backend/database/railway_data.db')
        source_conn.row_factory = sqlite3.Row
        
        print("  Extracting quotas from seat_inventory...")
        query = "SELECT trip_id, date, quota_type FROM seat_inventory WHERE seats_available > 0"
        data = source_conn.execute(query).fetchall()
        
        masks = defaultdict(int)
        for r in data:
            internal_trip_id = r['trip_id']
            if internal_trip_id in trip_to_train:
                t_no = trip_to_train[internal_trip_id]
                q_type = r['quota_type'].upper() if r['quota_type'] else "GN"
                mask_val = QUOTA_MAP.get(q_type, 1) # Default GN
                masks[(t_no, str(r['date']))] |= mask_val
                
        insert_data = [(k[0], k[1], v) for k, v in masks.items()]
        
        if insert_data:
            conn.executemany("INSERT INTO train_quota_masks VALUES (?, ?, ?)", insert_data)
            print(f"🎉 Successfully built quota masks for {len(insert_data)} train-days.")
        else:
            print("⚠️ No inventory data found. Creating default masks.")
            # Default to GN for all trains
            trains = [r[0] for r in conn.execute("SELECT trip_id FROM trips").fetchall()]
            from datetime import date, timedelta
            today = date.today()
            default_data = []
            for t in trains:
                for d in range(30):
                    default_data.append((t, (today + timedelta(days=d)).isoformat(), 1))
            conn.executemany("INSERT INTO train_quota_masks VALUES (?, ?, ?)", default_data)
            print(f"🎉 Created default quota masks for {len(default_data)} entries.")

        conn.commit()
        source_conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    build_quota_masks()
