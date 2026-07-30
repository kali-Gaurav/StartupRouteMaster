import sys
import os
import struct

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.session import SessionTransit
from sqlalchemy import text

INDEX_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'risk_index.bin')

def build_binary_index():
    print("🛠️ Building High-Performance Binary Risk Index...")
    db = SessionTransit()
    
    try:
        # Fetch all zones
        query = text("SELECT latitude, longitude, risk_level FROM risk_zones")
        results = db.execute(query).fetchall()
        
        # Sort by latitude for binary search sweep-line
        sorted_zones = sorted(results, key=lambda x: x[0])
        
        risk_map = {"low": 1, "medium": 3, "high": 5, "critical": 8}
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
        
        # Pack into dense binary format:
        # Each record: [float32 lat] [float32 lng] [uint8 risk_score] = 9 bytes total
        with open(INDEX_FILE, 'wb') as f:
            for lat, lng, level in sorted_zones:
                score = risk_map.get(level, 1)
                # 'ffB' = 2x 4-byte floats + 1x 1-byte unsigned char
                packed = struct.pack('ffB', lat, lng, score)
                f.write(packed)
                
        file_size = os.path.getsize(INDEX_FILE)
        print(f"✅ Binary index built successfully: {INDEX_FILE}")
        print(f"📊 Total Zones Packed: {len(sorted_zones)}")
        print(f"🗜️ Total File Size: {file_size / 1024:.2f} KB (Zero-Bloat)")

    finally:
        db.close()

if __name__ == "__main__":
    build_binary_index()
