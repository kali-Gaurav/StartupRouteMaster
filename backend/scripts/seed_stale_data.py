import sys
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database.session import SessionLocal
from database.models import TrainAvailabilityCache

def seed_stale_data():
    print("🧪 Seeding Stale Inventory Data for Verification...")
    db = SessionLocal()
    try:
        # Create a few very old records
        trains = [
            {"train_number": "12301", "coach_class": "SL", "age_hours": 12},
            {"train_number": "12951", "coach_class": "AC3", "age_hours": 8},
            {"train_number": "22415", "coach_class": "AC2", "age_hours": 5}
        ]
        
        for t in trains:
            # Delete existing to avoid dups
            db.query(TrainAvailabilityCache).filter(TrainAvailabilityCache.train_number == t["train_number"]).delete()
            
            stale_time = datetime.utcnow() - timedelta(hours=t["age_hours"])
            new_cache = TrainAvailabilityCache(
                train_number=t["train_number"],
                from_station_code="NDLS",
                to_station_code="BCT",
                journey_date=datetime.utcnow().date(),
                class_type=t["coach_class"],
                quota="GN",
                last_updated_at=stale_time,
                status_text="STALE_TEST"
            )
            db.add(new_cache)
            print(f"  ✅ Seeded Train {t['train_number']} (Age: {t['age_hours']}h)")
            
        db.commit()
        print("🚀 Seeding complete. Check 'Stale Data Leaderboard' in Admin Dashboard.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_stale_data()
