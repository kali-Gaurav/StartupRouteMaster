
import sqlite3
import os
import sys
from sqlalchemy import text

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from database.session import SessionLocal

def sync_stops():
    print("🔄 Syncing stops (UPSERT) to Supabase...")
    
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, stop_id, code, name, city, state, latitude, longitude FROM stops")
    stops = cursor.fetchall()
    conn.close()
    print(f"📦 Loaded {len(stops)} stops.")

    db = SessionLocal()
    try:
        batch_size = 200 # Smaller batches for remote PG
        for i in range(0, len(stops), batch_size):
            batch = stops[i:i+batch_size]
            values = []
            for s in batch:
                code = s[2] if s[2] else s[1]
                values.append({
                    "id": s[0], "stop_id": s[1], "code": code, "name": s[3],
                    "city": s[4], "state": s[5], "latitude": s[6], "longitude": s[7]
                })
            
            # PostgreSQL UPSERT
            stmt = text("""
                INSERT INTO stops (id, stop_id, code, name, city, state, latitude, longitude, safety_score, is_major_junction, facilities_json, wheelchair_accessible)
                VALUES (:id, :stop_id, :code, :name, :city, :state, :latitude, :longitude, 50.0, false, '{}', false)
                ON CONFLICT (id) DO UPDATE SET
                    stop_id = EXCLUDED.stop_id,
                    code = EXCLUDED.code,
                    name = EXCLUDED.name,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude
            """)
            db.execute(stmt, values)
            db.commit()
            if (i // batch_size) % 5 == 0:
                print(f"✅ Synced {i + len(batch)} stops...")
        
        print("🎉 SYNC COMPLETE!")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sync_stops()
