import sqlite3
import os

db_path = 'backend/database/transit_graph.db'

def seed_irctc_2026_fares():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Updating class_fare_matrix and creating fare_slabs (Task 1.14/7.3)...")
    
    # 1. Update Base per-km Rates (used after slab thresholds)
    fare_base_rates = [
        ('SL', 0.60),  # approx incremental
        ('3A', 1.50),
        ('2A', 2.20),
        ('1A', 4.50)
    ]
    cursor.execute("DELETE FROM class_fare_matrix")
    cursor.executemany("INSERT INTO class_fare_matrix VALUES (?, ?)", fare_base_rates)

    # 2. Create and Seed Slab Rates (Production-grade 2026 rates)
    cursor.execute("DROP TABLE IF EXISTS fare_slabs")
    cursor.execute("""
        CREATE TABLE fare_slabs (
            class_code TEXT,
            min_km INTEGER,
            max_km INTEGER,
            base_fare REAL
        )
    """)

    # Based on user-provided 2026 data:
    # 1-300km: SL 175, 3A 440, 2A 625, 1A 1059
    # 301-310km: SL 182, 3A 492, 2A 704, 1A 1190
    slabs = [
        ('SL', 1, 300, 175.0),
        ('3A', 1, 300, 440.0),
        ('2A', 1, 300, 625.0),
        ('1A', 1, 300, 1059.0),
        
        ('SL', 301, 310, 182.0),
        ('3A', 301, 310, 492.0),
        ('2A', 301, 310, 704.0),
        ('1A', 301, 310, 1190.0)
    ]
    cursor.executemany("INSERT INTO fare_slabs VALUES (?, ?, ?, ?)", slabs)

    conn.commit()
    conn.close()
    print("Production Fare Seeding Complete!")

if __name__ == "__main__":
    seed_irctc_2026_fares()
