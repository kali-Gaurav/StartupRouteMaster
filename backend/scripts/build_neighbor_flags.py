import sqlite3
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def build_neighbor_flags():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    
    print("🚀 Building Neighbor Fast-Check Flags (Suggestion #10)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS station_neighbor_flags")
        conn.execute("""
            CREATE TABLE station_neighbor_flags (
                station_id INTEGER PRIMARY KEY,
                has_neighbors INTEGER -- 1 if neighbors exist within 5km, else 0
            )
        """)
        
        # 2. Identify stations with neighbors from distance_cache (built in #9)
        # distance_cache already contains pairs within 10km. We'll filter for 5km.
        print("  Identifying stations with neighbors within 5km...")
        conn.execute("""
            INSERT INTO station_neighbor_flags (station_id, has_neighbors)
            SELECT id, 0 FROM stops
        """)
        
        conn.execute("""
            UPDATE station_neighbor_flags
            SET has_neighbors = 1
            WHERE station_id IN (
                SELECT DISTINCT src_id FROM distance_cache WHERE distance_km <= 5.0
            )
        """)
        
        conn.commit()
        
        # 3. Summary
        total = conn.execute("SELECT count(*) FROM station_neighbor_flags").fetchone()[0]
        has_neigh = conn.execute("SELECT count(*) FROM station_neighbor_flags WHERE has_neighbors = 1").fetchone()[0]
        print(f"🎉 Successfully flagged {has_neigh} / {total} stations as 'having neighbors'.")
        print(f"🚀 RAPTOR can now skip neighbor lookups for {total - has_neigh} isolated stations.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_neighbor_flags()
