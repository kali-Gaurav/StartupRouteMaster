import sqlite3
import json
import os

def export_stations_optimized():
    conn = sqlite3.connect('backend/database/railway_data.db')
    cursor = conn.cursor()
    
    # 1. Join stations with their frequency in transfers or stop_times to rank them
    # But for now, we use is_junction and a simple alphabetical/frequency heuristic
    query = """
    SELECT 
        station_code, 
        station_name, 
        city, 
        state, 
        is_junction
    FROM stations_master
    ORDER BY is_junction DESC, station_name ASC;
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    stations = []
    for row in rows:
        stations.append({
            "code": row[0],
            "name": row[1],
            "city": row[2],
            "state": row[3],
            "isJunction": bool(row[4])
        })
        
    print(f"Exported {len(stations)} stations.")
    
    # Writing to a TS file directly for the frontend to import
    output_path = 'src/data/stations_refined.ts'
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("/**\n * Optimized Station Dataset extracted from SQLite\n */\n")
        f.write("export interface Station {\n  code: string;\n  name: string;\n  city: string;\n  state: string;\n  isJunction: boolean;\n}\n\n")
        f.write("export const stationsRefined: Station[] = ")
        # Pretty print with indentation 2
        f.write(json.dumps(stations, indent=2))
        f.write(";\n")

if __name__ == "__main__":
    export_stations_optimized()
