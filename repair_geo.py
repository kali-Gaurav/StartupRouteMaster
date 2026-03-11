import sqlite3
import reverse_geocoder as rg
import os

db_path = 'backend/database/transit_graph.db'

def repair_geo():
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Fetching stops for geo-repair and normalization...")
    cursor.execute("SELECT id, latitude, longitude, code, name FROM stops")
    stops = cursor.fetchall()
    
    # Prepare data for batch reverse geocoding
    coordinates = [(s[1], s[2]) for s in stops]
    
    print(f"Performing batch reverse geocoding for {len(stops)} stops...")
    results = rg.search(coordinates) # This is fast and runs locally
    
    print("Updating database with repaired and normalized data...")
    updates = []
    for i, stop in enumerate(stops):
        stop_id_internal = stop[0]
        lat = stop[1]
        lon = stop[2]
        code = str(stop[3]).upper().strip() # Subtask 1.4 normalization
        
        res = results[i]
        city = res.get('name', '')
        state = res.get('admin1', '') # admin1 is usually state/province
        
        updates.append((code, city, state, stop_id_internal))

    cursor.executemany(
        "UPDATE stops SET code = ?, city = ?, state = ? WHERE id = ?",
        updates
    )

    conn.commit()
    conn.close()
    print("Geo-repair (1.3) and Normalization (1.4) Complete!")

if __name__ == "__main__":
    repair_geo()
