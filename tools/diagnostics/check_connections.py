import sqlite3

def check_connections(code):
    conn = sqlite3.connect('backend/database/transit_graph.db')
    query = """
        SELECT DISTINCT s2.code, s2.name 
        FROM stop_times st1 
        JOIN stop_times st2 ON st1.trip_id = st2.trip_id 
        JOIN stops s1 ON st1.stop_id = s1.id 
        JOIN stops s2 ON st2.stop_id = s2.id 
        WHERE s1.code = ? AND st1.stop_sequence < st2.stop_sequence 
        LIMIT 20
    """
    res = conn.execute(query, (code,)).fetchall()
    print(f"Connections from {code}: {res}")
    conn.close()

if __name__ == "__main__":
    check_connections('NDLS')
