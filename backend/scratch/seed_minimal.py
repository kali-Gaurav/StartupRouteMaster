
import asyncio
import os
import sys
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from database.session import SessionLocal, initialize_database_pools
from database.algorithm_models import StationKnowledge

async def seed_minimal():
    await initialize_database_pools()
    db = SessionLocal()
    try:
        stations = [
            ("NDLS", "New Delhi", "NR"),
            ("BCT", "Mumbai Central", "WR")
        ]
        for code, name, zone in stations:
            existing = db.query(StationKnowledge).filter(StationKnowledge.station_code == code).first()
            if not existing:
                sk = StationKnowledge(
                    station_code=code,
                    station_name=name,
                    zone=zone,
                    connectivity_score=0.9,
                    last_updated=datetime.utcnow()
                )
                db.add(sk)
                print(f"Seeded {code}")
            else:
                print(f"{code} already exists")
        db.commit()
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(seed_minimal())
