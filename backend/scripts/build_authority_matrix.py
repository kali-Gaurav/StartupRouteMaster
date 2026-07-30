import sys
import os
import math

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.session import SessionTransit
from sqlalchemy import text

def haversine(la1, lo1, la2, lo2):
    R = 6371.0
    dla, dlo = math.radians(la2-la1), math.radians(lo2-lo1)
    a = math.sin(dla/2)**2 + math.cos(math.radians(la1))*math.cos(math.radians(la2))*math.sin(dlo/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def build_matrix():
    print("🛠️ Pre-computing Authority Matrix for all stations...")
    db = SessionTransit()
    try:
        # 1. Fetch all authorities
        authorities = db.execute(text("SELECT id, latitude, longitude FROM emergency_authorities")).fetchall()
        if not authorities:
            print("❌ No authorities found in DB. Seed authorities first.")
            return

        # 2. Fetch all stations
        stations = db.execute(text("SELECT id, latitude, longitude FROM stations")).fetchall()
        print(f"Processing {len(stations)} stations...")

        # 3. For each station, find nearest authority
        update_query = text("UPDATE stations SET nearest_authority_id = :aid WHERE id = :sid")
        
        count = 0
        for sid, slat, slng in stations:
            if slat is None or slng is None: continue
            
            # Find closest authority
            nearest = min(authorities, key=lambda x: haversine(slat, slng, x[1], x[2]))
            
            db.execute(update_query, {"aid": nearest[0], "sid": sid})
            count += 1
            if count % 500 == 0:
                print(f"Updated {count} stations...")
                db.commit()
        
        db.commit()
        print(f"✅ Successfully pre-computed {count} station-to-authority mappings.")
        
    finally:
        db.close()

if __name__ == "__main__":
    build_matrix()
