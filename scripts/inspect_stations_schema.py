import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "backend" / "database" / "railway_data.db"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("PRAGMA table_info(stations)")
print("stations columns:", c.fetchall())
c.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN ('stations','station_search')")
print("tables:")
for row in c.fetchall():
    print(row)
conn.close()
