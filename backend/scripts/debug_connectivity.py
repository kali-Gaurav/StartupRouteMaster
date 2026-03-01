
import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find stations reachable from 111 (NDLS)
cursor.execute("SELECT DISTINCT dest_station_id FROM segments WHERE source_station_id='111'")
reachable_from_111 = {row[0] for row in cursor.fetchall()}

# Find stations that can reach 924 (BCT)
cursor.execute("SELECT DISTINCT source_station_id FROM segments WHERE dest_station_id='924'")
can_reach_924 = {row[0] for row in cursor.fetchall()}

common = reachable_from_111.intersection(can_reach_924)
print("Common stations for 1-transfer:", common)

if not common:
    print("No 1-transfer station found. Checking 2-transfers...")
    # Find stations reachable from NDLS via 1 stop
    cursor.execute("SELECT DISTINCT dest_station_id FROM segments WHERE source_station_id IN (SELECT DISTINCT dest_station_id FROM segments WHERE source_station_id='111')")
    reachable_2_hops = {row[0] for row in cursor.fetchall()}
    common_2 = reachable_2_hops.intersection(can_reach_924)
    print("Common stations for 2-transfer:", common_2)

conn.close()
