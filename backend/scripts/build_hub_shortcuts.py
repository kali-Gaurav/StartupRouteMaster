import sqlite3
import json
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def build_hub_shortcuts():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Hub-to-Hub Shortcut Index (Gap Analysis #4)...")
    
    try:
        # 1. Identify Major Hubs
        hub_rows = conn.execute("""
            SELECT s.code 
            FROM stops s 
            JOIN station_rank r ON s.id = r.station_id 
            WHERE r.hub_type = 'major_hub'
        """).fetchall()
        major_hubs = {r['code'] for r in hub_rows}
        print(f"  Found {len(major_hubs)} major hubs.")

        # 2. Extract backbone trains
        # We'll use the existing station_transit_index to find trains connecting these hubs
        conn.execute("DROP TABLE IF EXISTS hub_transit_index")
        conn.execute("""
            CREATE TABLE hub_transit_index (
                src_hub TEXT,
                dst_hub TEXT,
                trains_json TEXT,
                PRIMARY KEY (src_hub, dst_hub)
            )
        """)
        
        # This is a large cross-join potential, so we'll be smart.
        # We iterate over each train and see which major hubs it hits.
        train_hubs = defaultdict(list)
        
        # Get all station maps
        all_maps = conn.execute("SELECT station_code, trains_map FROM station_transit_index").fetchall()
        
        for row in all_maps:
            code = row['station_code']
            if code in major_hubs:
                trains = json.loads(row['train_map'] if 'train_map' in row.keys() else row['trains_map'])
                for t_no, details in trains.items():
                    # details: [dep, arr, mask, seq, dist, fare]
                    train_hubs[t_no].append({
                        "code": code,
                        "seq": details[3],
                        "dep": details[0],
                        "arr": details[1]
                    })
        
        # 3. Build src->dst mapping
        shortcuts = defaultdict(list)
        for t_no, hits in train_hubs.items():
            if len(hits) < 2: continue
            
            # Sort by sequence
            hits.sort(key=lambda x: x['seq'])
            
            for i in range(len(hits)):
                for j in range(i + 1, len(hits)):
                    src = hits[i]['code']
                    dst = hits[j]['code']
                    shortcuts[(src, dst)].append({
                        "t": t_no,
                        "d": hits[i]['dep'],
                        "a": hits[j]['arr']
                    })
        
        # 4. Insert
        print(f"  Inserting {len(shortcuts)} hub-to-hub pairs...")
        insert_data = [(pair[0], pair[1], json.dumps(trains)) for pair, trains in shortcuts.items()]
        conn.executemany("INSERT INTO hub_transit_index VALUES (?, ?, ?)", insert_data)
        
        conn.commit()
        print(f"🎉 Successfully built backbone index with {len(insert_data)} shortcuts.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    build_hub_shortcuts()
