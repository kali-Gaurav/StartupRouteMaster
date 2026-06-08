import sqlite3

def check_table(db_path, table_name):
    conn = sqlite3.connect(db_path)
    res = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'").fetchone()
    print(f"Table {table_name} in {db_path}: {res}")
    if res:
        count = conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        print(f"Row count: {count}")
    conn.close()

if __name__ == "__main__":
    check_table('backend/database/transit_graph.db', 'station_transit_index_bin')
    check_table('backend/database/railway_data.db', 'station_transit_index_bin')
    check_table('backend/database/transit_graph.db', 'hub_connectivity_index')
    check_table('backend/database/railway_data.db', 'hub_connectivity_index')
