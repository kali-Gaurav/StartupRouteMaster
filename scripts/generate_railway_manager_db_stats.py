import sqlite3
import os
import json
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
DB_PATH = os.path.join(ROOT, 'business', 'railway_data.db')

if not os.path.exists(DB_PATH):
    print(json.dumps({"error": "railway_data.db not found", "path": DB_PATH}))
    raise SystemExit(1)

stat = os.stat(DB_PATH)
info = {
    "path": DB_PATH,
    "size_bytes": stat.st_size,
    "size_kb": round(stat.st_size / 1024, 2),
    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    "tables": []
}

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()
# get tables and views
c.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name;")
items = c.fetchall()

total_rows = 0
for r in items:
    tname = r['name']
    try:
        c.execute(f'SELECT COUNT(*) AS cnt FROM "{tname}"')
        cnt = c.fetchone()['cnt']
    except Exception:
        cnt = None
    # columns
    cols = []
    try:
        c.execute(f'PRAGMA table_info("{tname}")')
        cols = [row['name'] for row in c.fetchall()]
    except Exception:
        cols = []
    # indexes
    idxs = []
    try:
        c.execute(f'PRAGMA index_list("{tname}")')
        idxs = [row['name'] for row in c.fetchall()]
    except Exception:
        idxs = []

    info['tables'].append({
        "name": tname,
        "type": r['type'],
        "rows": cnt,
        "columns": cols,
        "indexes": idxs
    })
    if isinstance(cnt, int):
        total_rows += cnt

info['total_tables'] = len(info['tables'])
info['total_rows'] = total_rows

print(json.dumps(info, indent=2, ensure_ascii=False))
conn.close()
