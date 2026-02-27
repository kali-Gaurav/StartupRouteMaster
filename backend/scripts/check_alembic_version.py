import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from database import engine

with engine.connect() as conn:
    try:
        rows = conn.execute(text("SELECT * FROM alembic_version")).fetchall()
        print('alembic_version rows:', rows)
    except Exception as e:
        print('alembic_version check error:', e)
