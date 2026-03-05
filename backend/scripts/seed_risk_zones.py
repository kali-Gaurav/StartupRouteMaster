import sys
import os
import random

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.session import SessionTransit
from sqlalchemy import text

def seed_risk_zones(count=10000):
    print(f"Seeding {count} mock risk zones...")
    db = SessionTransit()
    try:
        # Clear existing
        db.execute(text("DELETE FROM risk_zones"))
        
        # Base coordinates near Delhi and Mumbai
        centers = [(28.6139, 77.2090), (19.0760, 72.8777)]
        
        insert_query = text("""
            INSERT INTO risk_zones (id, latitude, longitude, risk_level, description)
            VALUES (:id, :lat, :lng, :level, :desc)
        """)
        
        for i in range(count):
            center = random.choice(centers)
            # Add random jitter (approx 50km radius)
            lat = center[0] + random.uniform(-0.5, 0.5)
            lng = center[1] + random.uniform(-0.5, 0.5)
            
            level = random.choice(["high", "medium", "low"])
            desc = f"Mock Zone {i}"
            
            db.execute(insert_query, {
                "id": f"zone-{i}",
                "lat": round(lat, 5),
                "lng": round(lng, 5),
                "level": level,
                "desc": desc
            })
            
            if i > 0 and i % 2000 == 0:
                print(f"Inserted {i}...")
                db.commit()
                
        db.commit()
        print(f"✅ Seeding complete. Total zones: {count}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_risk_zones()
