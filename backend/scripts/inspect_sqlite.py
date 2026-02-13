import sqlite3
import os
p = os.path.join(os.path.dirname(__file__), '..', 'railway_manager.db')
conn = sqlite3.connect(p)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table';")
print('tables =', c.fetchall())
for t in ['train_routes','train_schedule','stations_master']:
    try:
        c.execute(f'SELECT count(*) FROM {t}')
        print(f'{t} rows =', c.fetchone()[0])
    except Exception as e:
        print(f'{t} missing or error:', e)
conn.close()
