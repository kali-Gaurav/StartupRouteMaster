import sys
import os
import math

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.session import SessionTransit
from sqlalchemy import text

BITMAP_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'deadzones.bmp')

# India Bounding Box
MIN_LAT = 8.0
MAX_LAT = 38.0
MIN_LNG = 68.0
MAX_LNG = 98.0

# 1 degree is roughly 111 km. Let's make the grid 1km x 1km.
GRID_SIZE_LAT = int((MAX_LAT - MIN_LAT) * 111)
GRID_SIZE_LNG = int((MAX_LNG - MIN_LNG) * 111)

def build_bitmap():
    print("📡 Building 1km x 1km Dead-Zone Spatial Bitmap...")
    db = SessionTransit()
    
    # 1. Initialize a bytearray of zeros (1 bit per cell)
    total_cells = GRID_SIZE_LAT * GRID_SIZE_LNG
    total_bytes = math.ceil(total_cells / 8)
    bitmap = bytearray(total_bytes)
    
    try:
        # 2. Fetch dead zones
        query = text("SELECT latitude, longitude, radius_km FROM signal_dead_zones")
        results = db.execute(query).fetchall()
        
        # We will seed some dummy ones if empty for testing
        if not results:
            results = [(28.6, 77.2, 5.0), (19.0, 72.8, 3.0), (15.0, 75.0, 10.0)]
            
        print(f"Applying {len(results)} dead zone footprints to grid...")
        
        # 3. Apply bits (1) for dead zones
        for lat, lng, radius in results:
            if not (MIN_LAT <= lat <= MAX_LAT and MIN_LNG <= lng <= MAX_LNG):
                continue
                
            # Rasterize a circle onto the grid
            lat_idx_center = int((lat - MIN_LAT) * 111)
            lng_idx_center = int((lng - MIN_LNG) * 111)
            r_cells = int(radius)
            
            for d_lat in range(-r_cells, r_cells + 1):
                for d_lng in range(-r_cells, r_cells + 1):
                    # Check if inside circle radius
                    if d_lat**2 + d_lng**2 <= r_cells**2:
                        y = lat_idx_center + d_lat
                        x = lng_idx_center + d_lng
                        
                        if 0 <= y < GRID_SIZE_LAT and 0 <= x < GRID_SIZE_LNG:
                            cell_idx = y * GRID_SIZE_LNG + x
                            byte_idx = cell_idx // 8
                            bit_offset = cell_idx % 8
                            bitmap[byte_idx] |= (1 << bit_offset)
                            
        # 4. Save to file
        os.makedirs(os.path.dirname(BITMAP_FILE), exist_ok=True)
        with open(BITMAP_FILE, 'wb') as f:
            f.write(bitmap)
            
        print(f"✅ Bitmap built successfully: {BITMAP_FILE}")
        print(f"🗜️ Total File Size: {total_bytes / (1024*1024):.2f} MB")
        print(f"🗺️ Spatial Resolution: 1km square accuracy.")
        
    finally:
        db.close()

if __name__ == "__main__":
    build_bitmap()
