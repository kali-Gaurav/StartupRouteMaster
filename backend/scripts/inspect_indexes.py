import sys
from pathlib import Path
# ensure project root is on sys.path so 'backend' package can be imported when run as a script
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from database import engine

with engine.connect() as conn:
    tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))
    print('tables:', tables.fetchall())
    idxs = conn.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename='stations'"))
    print('stations indexes:', idxs.fetchall())
    all_idxs = conn.execute(text("SELECT indexname, tablename FROM pg_indexes WHERE schemaname='public' ORDER BY tablename, indexname"))
    print('all public indexes:', all_idxs.fetchall())
