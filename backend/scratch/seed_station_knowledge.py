
import os
import sys
import sqlite3
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from database.session import SessionLocal, initialize_database_pools
from database.algorithm_models import StationKnowledge

async def seed_stations():
    # 1. Connect to Transit DB (SQLite)
    transit_db_path = "backend/database/transit_graph.db"
    if not os.path.exists(transit_db_path):
        print(f"Transit DB not found at {transit_db_path}")
        return
    
    await initialize_database_pools()
    
    conn = sqlite3.connect(transit_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT stop_id, code, name, city, state, latitude, longitude, zone FROM stops")
    stops = cursor.fetchall()
    conn.close()
    
    print(f"Found {len(stops)} stops in transit DB.")
    
    # 2. Connect to User DB (Postgres)
    db = SessionLocal()
    try:
        count = 0
        for stop_id, code, name, city, state, lat, lon, zone in stops:
            # Check if exists
            existing = db.query(StationKnowledge).filter(StationKnowledge.station_code == code).first()
            if not existing:
                sk = StationKnowledge(
                    station_code=code,
                    station_name=name,
                    zone=zone,
                    connectivity_score=0.5,
                    last_updated=datetime.utcnow()
                )
                db.add(sk)
                count += 1
                if count % 100 == 0:
                    db.commit()
                    print(f"Seeded {count} stations...")
        
        db.commit()
        print(f"Finished seeding {count} stations.")
    except Exception as e:
        print(f"Error seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_stations())
