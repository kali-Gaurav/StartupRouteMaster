import sqlite3
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path
from database.config import Config

def build_transfer_penalties():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building Transfer Penalty Heatmap (Suggestion #7)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS station_transfer_penalties")
        conn.execute("""
            CREATE TABLE station_transfer_penalties (
                station_id INTEGER PRIMARY KEY,
                penalty_minutes INTEGER
            )
        """)
        
        # 2. Fetch platform counts from stops
        rows = conn.execute("SELECT id, name, platform_count FROM stops").fetchall()
        
        base_min = getattr(Config, "TRANSFER_WINDOW_MIN", 15)
        
        penalties = []
        for r in rows:
            p_count = r['platform_count'] or 2 # Default to 2 if unknown
            # Heuristic: 1.5 mins per platform walk + base buffer
            penalty = int(base_min + (p_count * 1.5))
            penalties.append((r['id'], penalty))
            
        conn.executemany("INSERT INTO station_transfer_penalties VALUES (?, ?)", penalties)
        conn.commit()
        print(f"🎉 Successfully calculated transfer penalties for {len(penalties)} stations.")
        
        # Verification check
        ndls = conn.execute("""
            SELECT s.name, p.penalty_minutes 
            FROM stops s JOIN station_transfer_penalties p ON s.id = p.station_id 
            WHERE s.code = 'NDLS'
        """).fetchone()
        if ndls:
            print(f"  - NDLS Penalty: {ndls[1]} minutes (Platform-aware)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_transfer_penalties()
