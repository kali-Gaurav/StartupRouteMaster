import sqlite3
import math
import os

db_path = 'backend/database/transit_graph.db'

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000 # Earth radius in METERS
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) * math.sin(dLat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon / 2) * math.sin(dLon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def generate_transfers():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Clearing existing transfers...")
    cursor.execute("DELETE FROM transfers")

    print("Fetching station coordinates...")
    cursor.execute("SELECT id, latitude, longitude, name FROM stops")
    stops = cursor.fetchall()
    
    transfers_to_insert = []
    
    print(f"Calculating transfers for {len(stops)} stations (1km threshold)...")
    
    # We use a simple nested loop but only within 1km. 
    # For 8.5k stations, N^2 is ~72M operations. Might be slow in pure Python.
    # Let's optimize by sorting by latitude or using a grid if needed.
    # However, for 8.5k, Python might handle it in a minute or two.
    
    # Optimization: Sort by latitude to prune search
    sorted_stops = sorted(stops, key=lambda x: x[1])
    
    for i in range(len(sorted_stops)):
        s1 = sorted_stops[i]
        for j in range(i + 1, len(sorted_stops)):
            s2 = sorted_stops[j]
            
            # Since sorted by latitude, if lat difference is > 1km, we can stop j loop
            # 1 degree lat is approx 111km. 1km is ~0.009 degrees.
            if (s2[1] - s1[1]) > 0.01:
                break
            
            dist = haversine(s1[1], s1[2], s2[1], s2[2])
            
            if dist <= 1000: # 1km threshold
                # Add bidirectional transfer
                # min_transfer_time: basic estimate (walking speed 5km/h = 1.4m/s) + 15 min buffer
                min_time = int((dist / 1.4) / 60) + 15 
                
                transfers_to_insert.append((s1[0], s2[0], min_time, round(dist, 2)))
                transfers_to_insert.append((s2[0], s1[0], min_time, round(dist, 2)))

        if len(transfers_to_insert) >= 5000:
            cursor.executemany(
                "INSERT INTO transfers (from_stop_id, to_stop_id, min_transfer_time, dist_meters) VALUES (?, ?, ?, ?)",
                transfers_to_insert
            )
            transfers_to_insert = []
            print(f"Inserted {i} stops worth of transfers...")

    if transfers_to_insert:
        cursor.executemany(
            "INSERT INTO transfers (from_stop_id, to_stop_id, min_transfer_time, dist_meters) VALUES (?, ?, ?, ?)",
            transfers_to_insert
        )

    conn.commit()
    conn.close()
    print("Transfers generation (1.8, 1.9) Complete!")

if __name__ == "__main__":
    generate_transfers()
