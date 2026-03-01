import sqlite3

def check_transfers_schema():
    conn = sqlite3.connect('backend/database/transit_graph.db')
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(transfers)")
        columns = cursor.fetchall()
        print("Columns in 'transfers' table:")
        for col in columns:
            print(col)
    except Exception as e:
        print(f"Error checking transfers table: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_transfers_schema()
