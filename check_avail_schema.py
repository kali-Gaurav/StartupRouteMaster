import sqlite3
conn = sqlite3.connect('backend/database/transit_graph.db')
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE name='train_availability_cache'")
print(c.fetchone()[0])
conn.close()
