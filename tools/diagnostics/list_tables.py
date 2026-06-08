import sqlite3
conn = sqlite3.connect('backend/database/transit_graph.db')
c = conn.cursor()
c.execute('SELECT name FROM sqlite_master WHERE type="table"')
print(c.fetchall())
conn.close()
