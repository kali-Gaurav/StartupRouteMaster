
import sqlite3
import os

db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Hub Connectivity Audit ---")
cursor.execute("SELECT count(*) FROM hub_connectivity_index")
print(f"Total Hub-to-Hub pairs indexed: {cursor.fetchone()[0]}")

print("\n--- Sample Hub Connectivity ---")
cursor.execute("SELECT src_hub_id, dst_hub_id, trains_json FROM hub_connectivity_index LIMIT 3")
for row in cursor.fetchall():
    print(f"Pair: {row[0]} -> {row[1]}, JSON length: {len(row[2])}")

print("\n--- Station Cluster Mapping Count ---")
cursor.execute("SELECT count(*) FROM station_cluster_mapping")
print(f"Total Clustered Stations: {cursor.fetchone()[0]}")

print("\n--- Check if NDLS (5533) is in any hub pairs ---")
cursor.execute("SELECT count(*) FROM hub_connectivity_index WHERE src_hub_id = 5533 OR dst_hub_id = 5533")
print(f"NDLS Hub Pairs: {cursor.fetchone()[0]}")

conn.close()
