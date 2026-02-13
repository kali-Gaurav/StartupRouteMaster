import sqlite3, json, os, sys
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'backend', 'railway_manager01.db')
DB_PATH = os.path.normpath(DB_PATH)
if not os.path.exists(DB_PATH):
    print(json.dumps({'error': f"DB file not found: {DB_PATH}"}))
    sys.exit(2)
con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
out = {}
for t in tables:
    cols = cur.execute(f"PRAGMA table_info('{t}')").fetchall()
    out[t] = [{"cid": c[0], "name": c[1], "type": c[2], "notnull": bool(c[3]), "default": c[4], "pk": c[5]} for c in cols]
print(json.dumps(out, indent=2))
con.close()
