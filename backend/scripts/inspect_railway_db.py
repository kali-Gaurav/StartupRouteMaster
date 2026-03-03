import sqlite3, os

db = 'backend/database/railway_data.db'
print('DB path:', db, 'exists:', os.path.exists(db))
conn = sqlite3.connect(db)
cur = conn.cursor()

print('\nTables:')
for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"):
    print(' -', r[0])

cands = ['train_routes','stations','schedules','trains','route_segments','station_schedules','station_stop_times']
print('\nCandidate table details:')
for t in cands:
    try:
        cur.execute(f'PRAGMA table_info({t})')
        cols = cur.fetchall()
        if cols:
            print(f'\n{t} columns: ', [c[1] for c in cols])
            cur.execute(f'SELECT * FROM {t} LIMIT 3')
            rows = cur.fetchall()
            for row in rows:
                print('  ', row)
        else:
            print(f'\n{t}: not present')
    except Exception as e:
        print(f'\n{t}: error -> {e}')

conn.close()
