import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Create table for Authorities
c.execute("""
    CREATE TABLE IF NOT EXISTS emergency_authorities (
        id VARCHAR(36) PRIMARY KEY,
        type VARCHAR(50) NOT NULL, -- 'RPF', 'GRP', 'HOSPITAL', 'FIRE'
        name VARCHAR(255) NOT NULL,
        station_code VARCHAR(50),
        latitude FLOAT NOT NULL,
        longitude FLOAT NOT NULL,
        contact_number VARCHAR(50),
        response_time_mins INTEGER DEFAULT 5
    )
""")

# Create spatial index for fast lookups
c.execute("CREATE INDEX IF NOT EXISTS idx_auth_location ON emergency_authorities(latitude, longitude)")
c.execute("CREATE INDEX IF NOT EXISTS idx_auth_station ON emergency_authorities(station_code)")

# Seed with dummy data for major hubs
authorities = [
    ('auth-1', 'RPF', 'New Delhi RPF Post', 'NDLS', 28.6428, 77.2190, '+91-11-23363322', 2),
    ('auth-2', 'HOSPITAL', 'Railway Hospital Delhi', 'NDLS', 28.6440, 77.2200, '+91-11-102', 8),
    ('auth-3', 'GRP', 'Mumbai Central GRP', 'BCT', 18.9696, 72.8193, '+91-22-23075056', 3),
    ('auth-4', 'HOSPITAL', 'Wockhardt Hospital', 'BCT', 18.9710, 72.8200, '+91-22-102', 10),
    ('auth-5', 'RPF', 'Kanpur RPF Headquarters', 'CNB', 26.4533, 80.3245, '+91-512-139', 4),
    ('auth-6', 'HOSPITAL', 'Sanjeevani Medical', 'CNB', 26.4550, 80.3260, '+91-512-102', 12)
]

c.executemany("INSERT OR REPLACE INTO emergency_authorities VALUES (?,?,?,?,?,?,?,?)", authorities)
conn.commit()
conn.close()
print("✅ emergency_authorities table created and seeded in transit_graph.db")
