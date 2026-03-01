import sqlite3

def check_db():
    conn = sqlite3.connect('backend/database/transit_graph.db')
    cursor = conn.cursor()
    
    tables = ['stops', 'routes', 'trips', 'stop_times', 'calendar']
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"Table {table}: {count} rows")
            
            if table == 'stops' and count > 0:
                cursor.execute(f"SELECT code, name FROM {table} LIMIT 5")
                print(f"Sample stops: {cursor.fetchall()}")
        except Exception as e:
            print(f"Error checking table {table}: {e}")
            
    conn.close()

if __name__ == "__main__":
    conn = sqlite3.connect('backend/database/transit_graph.db')
    cursor = conn.cursor()
    cursor.execute("SELECT code, name FROM stops WHERE name LIKE '%Mumbai Central%'")
    print(f"Mumbai Central Search result: {cursor.fetchall()}")
    conn.close()
    check_db()
