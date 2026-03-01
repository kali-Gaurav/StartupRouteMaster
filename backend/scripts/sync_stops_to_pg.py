
import sqlite3
import os
import sys
from sqlalchemy import text

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from database.session import SessionLocal, engine_write

def sync_stops():
    print("🔄 Syncing stops from TransitGraph (SQLite) to Supabase (Postgres)...")
    
    # 1. Load from SQLite
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, stop_id, code, name, city, state, latitude, longitude FROM stops")
    stops = cursor.fetchall()
    conn.close()
    print(f"📦 Loaded {len(stops)} stops from SQLite.")

    # 2. Insert into Postgres
    db = SessionLocal()
    try:
        # Clear existing stops to avoid ID conflicts
        db.execute(text("TRUNCATE TABLE stops CASCADE"))
        
        # Batch insert for speed
        batch_size = 500
        for i in range(0, len(stops), batch_size):
            batch = stops[i:i+batch_size]
            values = []
            for s in batch:
                # Use stop_id as code fallback if code is None
                code = s[2] if s[2] else s[1]
                values.append({
                    "id": s[0],
                    "stop_id": s[1],
                    "code": code,
                    "name": s[3],
                    "city": s[4],
                    "state": s[5],
                    "latitude": s[6],
                    "longitude": s[7],
                    "safety_score": 50.0,
                    "is_major_junction": False,
                    "facilities_json": "{}",
                    "wheelchair_accessible": False
                })
            
            stmt = text("""
                INSERT INTO stops (id, stop_id, code, name, city, state, latitude, longitude, safety_score, is_major_junction, facilities_json, wheelchair_accessible)
                VALUES (:id, :stop_id, :code, :name, :city, :state, :latitude, :longitude, :safety_score, :is_major_junction, :facilities_json, :wheelchair_accessible)
            """)
            db.execute(stmt, values)
            print(f"✅ Synced batch {i//batch_size + 1}")
        
        db.commit()
        print("🎉 ALL STOPS SYNCED SUCCESSFULLY!")
    except Exception as e:
        print(f"❌ Error during sync: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sync_stops()
