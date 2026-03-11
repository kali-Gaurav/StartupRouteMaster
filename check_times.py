import sqlite3
conn = sqlite3.connect('backend/database/transit_graph.db')
c = conn.cursor()
c.execute("SELECT departure_time FROM stop_times WHERE departure_time > '23:59:59' LIMIT 5")
print(c.fetchall())
conn.close()
