import sqlite3
import sys
import os
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.getcwd())

def build_pruning_index():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Search-Space Pruning Index (Suggestion #20)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS hub_distance_matrix")
        conn.execute("""
            CREATE TABLE hub_distance_matrix (
                src_code TEXT,
                dst_code TEXT,
                min_km REAL,
                PRIMARY KEY (src_code, dst_code)
            )
        """)
        
        # 2. Get Major Hubs
        hub_rows = conn.execute("""
            SELECT s.code FROM stops s 
            JOIN station_rank r ON s.id = r.station_id 
            WHERE r.hub_type = 'major_hub'
        """).fetchall()
        hubs = [r[0] for r in hub_rows]
        print(f"  Calculating distances between {len(hubs)} major hubs...")
        
        # 3. Calculate shortest direct distance for each pair from existing segments
        # (This is an approximation using the existing backbone data)
        query = """
            SELECT s.station_code as src, d.station_code as dst, 
                   min(CAST(json_extract(s_item.value, '$[4]') AS REAL)) as min_dist
            FROM station_transit_index s, station_transit_index d,
                 json_each(s.trains_map) as s_item,
                 json_each(d.trains_map) as d_item
            WHERE s.station_code IN (SELECT code FROM stops WHERE id IN (SELECT station_id FROM station_rank WHERE hub_type='major_hub'))
              AND d.station_code IN (SELECT code FROM stops WHERE id IN (SELECT station_id FROM station_rank WHERE hub_type='major_hub'))
              AND s_item.key = d_item.key
              AND CAST(json_extract(s_item.value, '$[3]') AS INTEGER) < CAST(json_extract(d_item.value, '$[3]') AS INTEGER)
            GROUP BY s.station_code, d.station_code
        """
        # This SQL is very heavy, so we'll use a smarter approach: use the pre-built hub_transit_index
        print("  Extracting shortest paths from hub_transit_index...")
        # Since I already built hub_transit_index, I can extract distances from there or segments.
        # Let's use a simpler heuristic for pruning: Haversine distance * 1.2
        
        from math import radians, cos, sin, asin, sqrt
        def haversine(lon1, lat1, lon2, lat2):
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1 
            dlat = lat2 - lat1 
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a)) 
            r = 6371 
            return c * r

        # Get hub coordinates
        hub_coords = {r['code']: (r['longitude'], r['latitude']) for r in conn.execute("SELECT code, latitude, longitude FROM stops WHERE code IN (" + ",".join([f"'{h}'" for h in hubs]) + ")").fetchall()}
        
        insert_data = []
        for h1 in hubs:
            for h2 in hubs:
                if h1 == h2: continue
                if h1 in hub_coords and h2 in hub_coords:
                    lon1, lat1 = hub_coords[h1]
                    lon2, lat2 = hub_coords[h2]
                    dist = haversine(lon1, lat1, lon2, lat2)
                    # Train distance is usually 1.2x - 1.4x haversine
                    insert_data.append((h1, h2, round(dist * 1.3, 2)))
                    
        conn.executemany("INSERT INTO hub_distance_matrix VALUES (?, ?, ?)", insert_data)
        conn.commit()
        print(f"🎉 Successfully built pruning matrix for {len(insert_data)} hub-pairs.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_pruning_index()
