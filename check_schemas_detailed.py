import sqlite3

def check_schema(db_path, table_name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(f"\n--- Schema for {table_name} in {db_path} ---")
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        for row in cursor.fetchall():
            print(row)
    except Exception as e:
        print(f"Error: {e}")
    conn.close()

if __name__ == "__main__":
    check_schema('backend/database/transit_graph.db', 'fares')
    check_schema('backend/database/transit_graph.db', 'segments')
    check_schema('backend/database/railway_data.db', 'train_fares')
    check_schema('backend/database/transit_graph.db', 'coaches')
