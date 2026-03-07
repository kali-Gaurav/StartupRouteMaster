import sqlite3

def check_trips_and_stops(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(f"\n--- Checking {db_path} ---")
    
    print("\nTrips sample:")
    cursor.execute("SELECT * FROM trips LIMIT 2")
    for row in cursor.fetchall():
        print(row)
        
    print("\nStops sample:")
    cursor.execute("SELECT * FROM stops LIMIT 2")
    for row in cursor.fetchall():
        print(row)
        
    conn.close()

if __name__ == "__main__":
    check_trips_and_stops('backend/database/transit_graph.db')
