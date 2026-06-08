import sqlite3
import os

db_path = "backend/database/transit_graph.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
try:
    row = conn.execute("SELECT id, code, name, centrality_score FROM stops WHERE id = 125").fetchone()
    if row:
        print(dict(row))
    else:
        print("Not found")
finally:
    conn.close()
