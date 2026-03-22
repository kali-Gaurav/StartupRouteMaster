
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("""
    SELECT s2.code 
    FROM station_cluster_mapping scm1 
    JOIN station_cluster_mapping scm2 ON scm1.cluster_id = scm2.cluster_id 
    JOIN stops s1 ON scm1.station_id = s1.id 
    JOIN stops s2 ON scm2.station_id = s2.id 
    WHERE s1.code = 'MMCT'
""")
codes = [r[0] for r in cursor.fetchall()]
print(f"MMCT Cluster: {codes}")
print(f"Is BDTS in cluster? {'BDTS' in codes}")
conn.close()
