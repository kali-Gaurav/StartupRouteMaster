import sqlite3

def check_trip_service(trip_id):
    conn = sqlite3.connect('backend/database/transit_graph.db')
    row = conn.execute("SELECT service_id FROM trips WHERE trip_id = ?", (trip_id,)).fetchone()
    if row:
        service_id = row[0]
        print(f"Service ID for {trip_id}: {service_id}")
        cal = conn.execute("SELECT * FROM calendar WHERE service_id = ?", (service_id,)).fetchone()
        print(f"Calendar for {service_id}: {cal}")
    else:
        print(f"Trip {trip_id} not found")
    conn.close()

if __name__ == "__main__":
    check_trip_service('12138')
