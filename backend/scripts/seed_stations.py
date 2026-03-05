import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.session import SessionTransit
from sqlalchemy import text

def seed_stations():
    print("🚉 Seeding sample stations...")
    db = SessionTransit()
    try:
        # 1. Major stations
        data = [
            ("NDLS", "New Delhi", "Delhi", 28.6428, 77.2190),
            ("BCT", "Mumbai Central", "Mumbai", 18.9697, 72.8194),
            ("CNB", "Kanpur Central", "Kanpur", 26.4547, 80.3513),
            ("SBC", "Bangalore City", "Bangalore", 12.9781, 77.5697),
            ("MAS", "Chennai Central", "Chennai", 13.0827, 80.2707)
        ]
        
        insert_query = text("""
            INSERT INTO stations (id, name, city, latitude, longitude)
            VALUES (:id, :name, :city, :lat, :lng)
        """)
        
        for sid, name, city, lat, lng in data:
            db.execute(insert_query, {"id": sid, "name": name, "city": city, "lat": lat, "lng": lng})
            
        db.commit()
        print(f"✅ Seeded {len(data)} stations.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_stations()
