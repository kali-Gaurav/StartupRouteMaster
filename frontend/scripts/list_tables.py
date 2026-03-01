import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "backend" / "database" / "railway_data.db"
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for row in c.fetchall():
    print(row[0])
conn.close()
