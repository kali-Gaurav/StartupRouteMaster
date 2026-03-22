
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def get_clusters(code):
    cursor.execute("""
        SELECT cluster_id FROM station_cluster_mapping scm
        JOIN stops s ON s.id = scm.station_id
        WHERE s.code = ?
    """, (code,))
    return [r[0] for r in cursor.fetchall()]

ms_clusters = get_clusters('MS')
mas_clusters = get_clusters('MAS')

print(f"MS Clusters: {ms_clusters}")
print(f"MAS Clusters: {mas_clusters}")

# Check if they share any cluster
shared = set(ms_clusters).intersection(set(mas_clusters))
print(f"Shared Clusters: {shared}")

conn.close()
