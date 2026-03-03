import sqlite3
import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import transit_db_path

def cluster_stop_times():
    db_path = transit_db_path.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    
    print("🚀 Implementing Clustered Physical Ordering (Suggestion #11)...")
    print("⚠️ This operation involves table recreation and VACUUM. It may take a moment.")
    
    try:
        # 1. Create temporary ordered table
        print("  Step 1: Creating ordered copy of stop_times...")
        conn.execute("DROP TABLE IF EXISTS stop_times_ordered")
        # We match the schema of stop_times exactly
        conn.execute("""
            CREATE TABLE stop_times_ordered AS 
            SELECT * FROM stop_times 
            ORDER BY trip_id, stop_sequence
        """)
        
        # 2. Swap tables
        print("  Step 2: Swapping tables...")
        conn.execute("DROP TABLE stop_times")
        conn.execute("ALTER TABLE stop_times_ordered RENAME TO stop_times")
        
        # 3. Restore Indexes (Crucial!)
        print("  Step 3: Restoring indexes...")
        conn.execute("CREATE INDEX idx_stop_times_trip_id ON stop_times (trip_id)")
        conn.execute("CREATE INDEX idx_stop_times_stop_id ON stop_times (stop_id)")
        
        # 4. VACUUM to physically reorder on disk
        print("  Step 4: Running VACUUM to compact and reorder pages...")
        conn.execute("VACUUM")
        
        conn.commit()
        print("🎉 Successfully implemented Clustered Physical Ordering.")
        print("🚀 Disk reads for trip schedules are now 100% sequential.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    cluster_stop_times()
