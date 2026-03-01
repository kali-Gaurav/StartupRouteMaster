import sqlite3, os
DB_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'railway_manager01.db'))
con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    cols = cur.execute(f"PRAGMA table_info('{t}')").fetchall()
    col_str = ', '.join([f"{c[0]}:{c[1]}" for c in cols])
    print(f"{t}: {col_str}")
con.close()
