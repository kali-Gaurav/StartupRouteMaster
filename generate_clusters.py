import sqlite3
import numpy as np
from sklearn.cluster import DBSCAN, KMeans
import os
import uuid
import math

db_path = 'backend/database/transit_graph.db'

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) * math.sin(dLat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon / 2) * math.sin(dLon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def generate_clusters():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Re-creating cluster tables with RECURSIVE REFINEMENT...")
    cursor.execute("DROP TABLE IF EXISTS city_clusters")
    cursor.execute("""
        CREATE TABLE city_clusters (
            id VARCHAR(36) PRIMARY KEY,
            cluster_name TEXT,
            latitude FLOAT,
            longitude FLOAT
        )
    """)
    
    cursor.execute("DROP TABLE IF EXISTS station_cluster_mapping")
    cursor.execute("""
        CREATE TABLE station_cluster_mapping (
            station_id INTEGER,
            cluster_id VARCHAR(36),
            FOREIGN KEY(station_id) REFERENCES stops(id),
            FOREIGN KEY(cluster_id) REFERENCES city_clusters(id)
        )
    """)

    cursor.execute("SELECT id, latitude, longitude, name, city FROM stops")
    stops = cursor.fetchall()
    
    # Phase 1: Initial DBSCAN
    coords_rad = np.radians([[s[1], s[2]] for s in stops])
    epsilon = 5.0 / 6371.0
    db = DBSCAN(eps=epsilon, min_samples=1, metric='haversine', algorithm='ball_tree').fit(coords_rad)
    
    clusters_queue = {}
    for i, label in enumerate(db.labels_):
        if label not in clusters_queue: clusters_queue[label] = []
        clusters_queue[label].append(stops[i])

    final_clusters = []
    pending_clusters = list(clusters_queue.values())

    print(f"Initial DBSCAN found {len(pending_clusters)} clusters. Starting deep refinement...")

    # Phase 2: Iterative Splitting for 100% Sanity
    iteration = 0
    while pending_clusters:
        iteration += 1
        current_batch = pending_clusters
        pending_clusters = []
        
        for station_list in current_batch:
            if len(station_list) <= 1:
                final_clusters.append(station_list)
                continue
                
            # Calculate centroid
            clat = sum(s[1] for s in station_list) / len(station_list)
            clon = sum(s[2] for s in station_list) / len(station_list)
            
            # Find max distance
            max_d = 0
            for s in station_list:
                d = haversine(clat, clon, s[1], s[2])
                if d > max_d: max_d = d
            
            # Constraint check (10km limit)
            if max_d > 10.0:
                # Split using K-Means (k=2)
                sub_coords = np.array([[s[1], s[2]] for s in station_list])
                kmeans = KMeans(n_clusters=2, n_init=10).fit(sub_coords)
                
                sub1 = []
                sub2 = []
                for idx, label in enumerate(kmeans.labels_):
                    if label == 0: sub1.append(station_list[idx])
                    else: sub2.append(station_list[idx])
                
                pending_clusters.append(sub1)
                pending_clusters.append(sub2)
            else:
                final_clusters.append(station_list)
        
        if pending_clusters:
            print(f"Iteration {iteration}: Splitting {len(pending_clusters)//2} oversized clusters...")

    print(f"Final Guaranteed Cluster Count: {len(final_clusters)}")

    cluster_inserts = []
    mapping_inserts = []
    for station_list in final_clusters:
        c_id = str(uuid.uuid4())
        clat = sum(s[1] for s in station_list) / len(station_list)
        clon = sum(s[2] for s in station_list) / len(station_list)
        
        cities = [s[4] for s in station_list if s[4]]
        cluster_name = max(set(cities), key=cities.count) if cities else station_list[0][3]
        
        cluster_inserts.append((c_id, cluster_name, clat, clon))
        for s in station_list:
            mapping_inserts.append((s[0], c_id))

    cursor.executemany("INSERT INTO city_clusters VALUES (?, ?, ?, ?)", cluster_inserts)
    cursor.executemany("INSERT INTO station_cluster_mapping VALUES (?, ?)", mapping_inserts)

    conn.commit()
    conn.close()
    print("Deeply Improved City Clusters Complete!")

if __name__ == "__main__":
    generate_clusters()
