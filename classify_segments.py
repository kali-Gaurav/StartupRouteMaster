import sqlite3
import os

db_path = 'backend/database/transit_graph.db'

def classify_segments():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Classifying segments into EXPRESS vs LOCAL (Task 1.13)...")
    # Speed = distance_km / (duration_minutes / 60)
    # Threshold for Express: 60 km/h (average between stops)
    
    # We'll use data_quality_score to store a bitmask or just use a simple value.
    # 1 for EXPRESS, 0 for LOCAL
    
    cursor.execute("""
        UPDATE segments 
        SET data_quality_score = CASE 
            WHEN duration_minutes > 0 AND (distance_km / (duration_minutes / 60.0)) >= 60.0 THEN 1 
            ELSE 0 
        END
    """)
    
    conn.commit()
    
    # Check counts
    cursor.execute("SELECT count(*) FROM segments WHERE data_quality_score = 1")
    express_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM segments WHERE data_quality_score = 0")
    local_count = cursor.fetchone()[0]
    
    print(f"Classification complete: {express_count} Express segments, {local_count} Local segments.")
    conn.close()

if __name__ == "__main__":
    classify_segments()
