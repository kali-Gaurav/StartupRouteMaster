import sqlite3
import os

db_path = 'backend/database/transit_graph.db'

def seed_fare_matrix():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Seeding class_fare_matrix with standard rates (Task 1.14)...")
    # Base rates per km (estimated IRCTC-like rates for seeding)
    # SL: 0.60 Rs/km
    # 3A: 1.50 Rs/km
    # 2A: 2.20 Rs/km
    # 1A: 4.50 Rs/km
    
    fare_data = [
        ('SL', 0.60),
        ('3A', 1.50),
        ('2A', 2.20),
        ('1A', 4.50)
    ]
    
    cursor.execute("DELETE FROM class_fare_matrix")
    cursor.executemany("INSERT INTO class_fare_matrix VALUES (?, ?)", fare_data)

    conn.commit()
    conn.close()
    print("Fare matrix seeding (1.14) Complete!")

if __name__ == "__main__":
    seed_fare_matrix()
