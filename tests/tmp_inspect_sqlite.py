import sqlite3, os
# Inspect the human-readable railway data source
p=os.path.join('backend','database','railway_data.db')
print('exists', os.path.exists(p), p)
conn=sqlite3.connect(p)
cur=conn.cursor()
for t in ['stations_master','train_routes','train_schedule','train_running_days']:
    try:
        cur.execute(f"select count(*) from {t}")
        print(t, cur.fetchone()[0])
    except Exception as e:
        print(t, 'ERROR', e)
conn.close()
