import sqlite3
import os
db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
try:
    print('--- station_cluster_mapping ---')
    cursor.execute("PRAGMA table_info('station_cluster_mapping')")
    print(cursor.fetchall())
    
    print('--- hub_distance_matrix ---')
    cursor.execute("PRAGMA table_info('hub_distance_matrix')")
    print(cursor.fetchall())
    
    cursor.execute("SELECT count(*) FROM hub_distance_matrix")
    print('hub_distance_matrix count:', cursor.fetchone()[0])
    
except Exception as e:
    print(f'Error: {e}')
finally:
    conn.close()
