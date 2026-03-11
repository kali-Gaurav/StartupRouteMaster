import sqlite3
conn = sqlite3.connect('backend/database/transit_graph.db')
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE name='route_shapes'")
print(cursor.fetchone()[0])
conn.close()
