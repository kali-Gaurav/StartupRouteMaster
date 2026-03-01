import sqlite3

def check_transit_data():
    conn = sqlite3.connect('backend/database/transit_graph.db')
    cursor = conn.cursor()
    
    train_no = 19024
    print(f"Checking data for train {train_no}...")
    
    cursor.execute("SELECT * FROM trips WHERE trip_id = ?", (str(train_no),))
    trip = cursor.fetchone()
    print(f"Trip: {trip}")
    
    if trip:
        trip_id = trip[0]
        cursor.execute("""
            SELECT s.code, st.arrival_time, st.departure_time, st.stop_sequence
            FROM stop_times st
            JOIN stops s ON st.stop_id = s.id
            WHERE st.trip_id = ?
            ORDER BY st.stop_sequence
        """, (trip_id,))
        schedule = cursor.fetchall()
        print(f"Schedule: {schedule}")
        
        cursor.execute("SELECT * FROM calendar WHERE service_id = ?", (trip[3],)) # service_id is 4th col
        cal = cursor.fetchone()
        print(f"Calendar: {cal}")

    conn.close()

if __name__ == "__main__":
    check_transit_data()
