import sqlite3
import os

databases = [
    'backend/database/railway_data.db',
    'backend/database/transit_graph.db',
    'backend/database/user_store.db'
]

def inspect_db(db_path):
    if not os.path.exists(db_path):
        print(f"Database {db_path} NOT FOUND")
        return
    
    print(f"\n--- Inspecting {db_path} ---")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"Table: {table_name:<25} | Rows: {count}")
            
            # Show top 2 rows if any
            if count > 0:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 2")
                rows = cursor.fetchall()
                # for row in rows:
                #    print(f"  Sample: {row}")
        
        conn.close()
    except Exception as e:
        print(f"Error inspecting {db_path}: {e}")

if __name__ == "__main__":
    for db in databases:
        inspect_db(db)
