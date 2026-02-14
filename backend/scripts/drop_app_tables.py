import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from backend.database import engine

sql = '''
DROP TABLE IF EXISTS unlocked_routes CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS segments CASCADE;
DROP TABLE IF EXISTS bookings CASCADE;
DROP TABLE IF EXISTS vehicles CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS stations_master CASCADE;
DROP TABLE IF EXISTS stations CASCADE;
DROP TABLE IF EXISTS routes CASCADE;
'''

with engine.connect() as conn:
    conn.execute(text(sql))
    conn.commit()

print('dropped app tables')
