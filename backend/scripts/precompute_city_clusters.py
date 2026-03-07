import sqlite3
import json
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("city_clusters")

def precompute_clusters():
    db_path = 'backend/database/transit_graph.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    logger.info("Discovering City Clusters...")
    
    # 1. Create Table
    cur.execute("DROP TABLE IF EXISTS city_clusters")
    cur.execute("""
        CREATE TABLE city_clusters (
            city_name TEXT PRIMARY KEY,
            station_codes_json TEXT
        )
    """)

    # 2. Group by City
    cur.execute("SELECT code, city FROM stops WHERE city IS NOT NULL AND city != ''")
    rows = cur.fetchall()
    
    clusters = defaultdict(list)
    for code, city in rows:
        clusters[city.upper().strip()].append(code.upper().strip())

    # 3. Filter clusters with > 1 station
    valid_clusters = []
    for city, codes in clusters.items():
        if len(codes) > 1:
            valid_clusters.append((city, json.dumps(list(set(codes)))))

    logger.info(f"Found {len(valid_clusters)} valid city clusters.")
    
    # 4. Insert
    cur.executemany("INSERT INTO city_clusters VALUES (?, ?)", valid_clusters)
    
    # 5. Add Manual Important Clusters (e.g., Delhi, Mumbai, Palakkad)
    manual = [
        ("PALAKKAD", json.dumps(["PGT", "PGTN", "OTP"])),
        ("DELHI", json.dumps(["NDLS", "NZM", "DLI", "ANVT", "DEC"])),
        ("MUMBAI", json.dumps(["BCT", "BDTS", "DR", "KYN", "PNVL", "CSTM"]))
    ]
    for city, codes in manual:
        cur.execute("INSERT OR REPLACE INTO city_clusters VALUES (?, ?)", (city, codes))

    conn.commit()
    conn.close()
    logger.info("City Cluster pre-computation complete.")

if __name__ == "__main__":
    precompute_clusters()
