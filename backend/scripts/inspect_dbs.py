import sqlite3
import os

dbs = [
    'backend/database/railway_data.db',
    'backend/database/transit_graph.db',
    'backend/database/user_store.db'
]

def get_schema(db_path):
    if not os.path.exists(db_path):
        return f"Database {db_path} not found."
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    schema_info = f"--- Schema for {db_path} ---\n"
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    for table_name in tables:
        table_name = table_name[0]
        schema_info += f"\nTable: {table_name}\n"
        
        # Get columns for each table
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        for col in columns:
            schema_info += f"  - {col[1]} ({col[2]})\n"
            
    conn.close()
    return schema_info

if __name__ == "__main__":
    full_report = ""
    for db in dbs:
        full_report += get_schema(db) + "\n"
    
    with open("database_schema_report.txt", "w", encoding='utf-8') as f:
        full_report = full_report.encode('ascii', 'ignore').decode('ascii')
        f.write(full_report)
    print("Schema report generated: database_schema_report.txt")
