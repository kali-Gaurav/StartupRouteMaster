import sys
import os
import struct

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.session import SessionTransit
from sqlalchemy import text

TOP_DANGER_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'top_danger.bin')

def build_top_danger():
    print("🚨 Building Cache-Local Top-100 Danger Zone Index...")
    db = SessionTransit()
    try:
        # Fetch top 100 critical/high zones
        query = text("""
            SELECT latitude, longitude, risk_level 
            FROM risk_zones 
            WHERE risk_level IN ('critical', 'high')
            LIMIT 100
        """)
        results = db.execute(query).fetchall()
        
        # Sort by lat for small sweep-line
        sorted_zones = sorted(results, key=lambda x: x[0])
        
        risk_map = {"low": 1, "medium": 3, "high": 5, "critical": 8}
        
        with open(TOP_DANGER_FILE, 'wb') as f:
            for lat, lng, level in sorted_zones:
                score = risk_map.get(level, 5)
                f.write(struct.pack('ffB', lat, lng, score))
                
        print(f"✅ Top-Danger index built: {TOP_DANGER_FILE}")
        print(f"📊 Packed {len(sorted_zones)} critical zones.")
        print(f"🗜️ Size: {os.path.getsize(TOP_DANGER_FILE)} bytes (Fits in L1 Cache)")
        
    finally:
        db.close()

if __name__ == "__main__":
    build_top_danger()
