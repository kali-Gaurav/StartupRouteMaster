import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("""
    CREATE TABLE IF NOT EXISTS signal_dead_zones (
        id VARCHAR(36) PRIMARY KEY,
        latitude FLOAT NOT NULL,
        longitude FLOAT NOT NULL,
        radius_km FLOAT DEFAULT 2.0,
        expected_duration_mins INTEGER DEFAULT 5,
        description TEXT
    )
""")

# Seed with a few known problematic areas (e.g., tunnels)
mock_zones = [
    ('tunnel-1', 19.7, 73.4, 3.0, 10, 'Western Ghats Tunnel Section'),
    ('mountain-pass', 32.2, 75.8, 5.0, 15, 'Jammu-Udhampur Mountain Pass')
]

c.executemany("INSERT OR REPLACE INTO signal_dead_zones VALUES (?,?,?,?,?,?)", mock_zones)
conn.commit()
conn.close()
print("signal_dead_zones table created and seeded.")
