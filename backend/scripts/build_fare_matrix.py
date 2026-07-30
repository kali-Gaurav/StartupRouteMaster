import sqlite3
import sys
import os

def build_fare_matrix():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    
    print("🚀 Building Static Fare Matrix (Suggestion #16)...")
    
    try:
        # 1. Create table
        conn.execute("DROP TABLE IF EXISTS class_fare_matrix")
        conn.execute("""
            CREATE TABLE class_fare_matrix (
                class_code TEXT PRIMARY KEY,
                base_fare_per_km REAL
            )
        """)
        
        # 2. Heuristic values based on Indian Railways standard base fares
        # (Standardized for fast estimation)
        fares = [
            ("SL", 0.45),
            ("3A", 1.15),
            ("2A", 1.65),
            ("1A", 2.80),
            ("CC", 1.05),
            ("EC", 2.20),
            ("2S", 0.25)
        ]
        
        conn.executemany("INSERT INTO class_fare_matrix VALUES (?, ?)", fares)
        conn.commit()
        print(f"🎉 Successfully indexed base fares for {len(fares)} coach classes.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_fare_matrix()
