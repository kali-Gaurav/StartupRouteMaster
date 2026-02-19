import sqlite3
import os
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
DB_PATH = os.path.join(ROOT, 'railway_manager.db')
OUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'docs', 'RAILWAY_MANAGER_DB_REPORT.md')

if not os.path.exists(DB_PATH):
    raise SystemExit(f"railway_manager.db not found at {DB_PATH}")

stat = os.stat(DB_PATH)
size_kb = stat.st_size / 1024.0
modified = datetime.fromtimestamp(stat.st_mtime).isoformat()

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name;")
items = c.fetchall()

rows = []
total_rows = 0
for name, typ in items:
    try:
        c.execute(f'SELECT COUNT(*) FROM "{name}"')
        cnt = c.fetchone()[0]
    except Exception:
        cnt = None
    rows.append((name, typ, cnt))
    if isinstance(cnt, int):
        total_rows += cnt

rows_sorted = sorted(rows, key=lambda r: (r[2] if r[2] is not None else -1), reverse=True)

# pick key tables for column listing
key_tables = ['stations_master', 'train_routes', 'stop_times', 'trains', 'train_schedule', 'segments', 'stations', 'fare_rules']
cols = {}
for t in key_tables:
    try:
        c.execute(f'PRAGMA table_info("{t}")')
        cols[t] = [r[1] for r in c.fetchall()]
    except Exception:
        cols[t] = None

conn.close()

md = []
md.append('# railway_manager.db — architecture & data inventory ✅\n')
md.append(f'**Location:** `backend/railway_manager.db`  
**File size:** {stat.st_size} bytes ({size_kb:.2f} KB)  
**Last modified:** {modified}  
')
md.append('---\n')
md.append('## Summary\n')
md.append(f'- **Total tables/views inspected:** {len(rows)}\n')
md.append(f'- **Aggregate row count (countable tables):** {total_rows:,}\n')
md.append('\n')
md.append('## Top tables by row count (top 12)\n')
md.append('| # | table | type | rows |\n')
md.append('|---:|---|---|---:|\n')
for i, (name, typ, cnt) in enumerate(rows_sorted[:12], start=1):
    md.append(f'| {i} | `{name}` | {typ} | {cnt if cnt is not None else "—":,} |\n')
md.append('\n')
md.append('## Full table inventory (name — rows)\n')
for name, typ, cnt in rows_sorted:
    md.append(f'- `{name}` ({typ}) — {cnt if cnt is not None else "unknown"}\n')
md.append('\n')
md.append('## Selected table schemas (key tables)\n')
for t in key_tables:
    if cols.get(t) is None:
        md.append(f'- `{t}` — **not present** or schema unavailable\n')
    else:
        md.append(f'### `{t}`\n')
        md.append('`' + '`, `'.join(cols[t]) + '`\n')
md.append('\n')
md.append('## Observations & recommendations\n')
md.append('- `railway_manager.db` is the authoritative local SQLite dataset used across the codebase for routing and ETL.\n')
md.append('- Large tables such as `stop_times` / `train_schedule` are the main contributors to storage and should be the focus of any incremental-sync or indexing efforts.\n')
md.append('- Recommendation: run the ETL (`backend/etl/sqlite_to_postgres.py`) on a schedule and keep `railway_manager.db` out of git for large/production copies.\n')
md.append('\n')
md.append('---\n')
md.append('_Report generated programmatically from the local `railway_manager.db` file._\n')

with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(md))

print(f'Wrote report to {OUT_PATH}')
