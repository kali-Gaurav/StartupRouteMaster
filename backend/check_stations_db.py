import sqlite3
conn = sqlite3.connect('backend/database/transit_graph.db')
cursor = conn.execute("SELECT * FROM stops WHERE code IN ('MMCT', 'BCL', 'NDLS', 'SBC', 'BNC', 'HWH', 'KOAA', 'SDAH')")
for row in cursor.fetchall():
    print(row)
conn.close()
