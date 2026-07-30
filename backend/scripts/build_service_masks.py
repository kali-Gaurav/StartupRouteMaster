import sqlite3
import datetime
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def build_365_day_masks():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🚀 Building 365-day Service Bitmasks (Suggestion #1)...")
    
    try:
        # 1. Create the Bitmask Table
        conn.execute("DROP TABLE IF EXISTS trip_service_masks")
        conn.execute("""
            CREATE TABLE trip_service_masks (
                trip_id INTEGER PRIMARY KEY,
                mask BLOB  -- 366 bits = 46 bytes
            )
        """)
        
        # 2. Fetch all trips and their calendar patterns
        # trips table links to calendar
        query = """
            SELECT t.id as trip_internal_id, c.monday, c.tuesday, c.wednesday, 
                   c.thursday, c.friday, c.saturday, c.sunday,
                   c.start_date, c.end_date
            FROM trips t
            JOIN calendar c ON t.service_id = c.service_id
        """
        trips = conn.execute(query).fetchall()
        
        base_date = datetime.date(2026, 1, 1)
        
        mask_data = []
        for trip in trips:
            # Create a bitset for the year
            # We use a bytearray to represent bits
            mask = bytearray(46) # 46 * 8 = 368 bits
            
            # Days of week: 0=Mon, 6=Sun
            days_enabled = [
                trip['monday'], trip['tuesday'], trip['wednesday'],
                trip['thursday'], trip['friday'], trip['saturday'], trip['sunday']
            ]
            
            # Fill the mask for the next 365 days
            for d_offset in range(366):
                curr_date = base_date + datetime.timedelta(days=d_offset)
                
                # Check weekday
                if days_enabled[curr_date.weekday()]:
                    # Set the bit
                    byte_idx = d_offset // 8
                    bit_idx = d_offset % 8
                    mask[byte_idx] |= (1 << bit_idx)
            
            mask_data.append((trip['trip_internal_id'], mask))
            
        conn.executemany("INSERT INTO trip_service_masks VALUES (?, ?)", mask_data)
        conn.commit()
        print(f"🎉 Successfully generated bitmasks for {len(mask_data)} trips.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_365_day_masks()
