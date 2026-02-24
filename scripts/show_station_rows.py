import sqlite3
from pathlib import Path
DB = Path(__file__).resolve().parents[1] / "backend" / "database" / "railway_data.db"
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT id, name, city, latitude, longitude FROM stations LIMIT 5")
for row in c.fetchall():
    print(row)
conn.close()
