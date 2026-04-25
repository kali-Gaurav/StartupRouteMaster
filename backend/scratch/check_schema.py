import sqlite3
try:
    conn = sqlite3.connect('database/transit_graph.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(cancelled_trains)")
    columns = cursor.fetchall()
    print("Columns in cancelled_trains:")
    for col in columns:
        print(col)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
