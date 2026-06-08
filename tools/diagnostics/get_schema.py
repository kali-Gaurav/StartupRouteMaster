import sqlite3
import os

def get_schema(db_path, table_name):
    if not os.path.exists(db_path):
        print(f"Database {db_path} NOT FOUND")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print(f"\n--- Schema for {table_name} in {db_path} ---")
    for col in columns:
        print(col)
    conn.close()

if __name__ == "__main__":
    get_schema('backend/database/user_store.db', 'route_search_logs')
    get_schema('backend/database/railway_data.db', 'route_search_logs')
    get_schema('backend/database/railway_data.db', 'route_knowledge')
    get_schema('backend/database/railway_data.db', 'demand_snapshots')
