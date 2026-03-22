
import sqlite3
db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT station_code FROM station_transit_index_bin WHERE station_code LIKE 'M%'")
codes = [r[0] for r in cursor.fetchall()]
print(f"Codes starting with M: {codes[:20]}")
print(f"Is MMCT present? {'MMCT' in codes}")
print(f"Is BCT present? {'BCT' in codes}")
cursor.execute("SELECT station_code FROM station_transit_index_bin WHERE station_code LIKE 'B%'")
codes_b = [r[0] for r in cursor.fetchall()]
print(f"Codes starting with B: {codes_b[:20]}")
conn.close()
