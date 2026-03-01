import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from database.session import engine_write
from sqlalchemy import text

def run_migration():
    with engine_write.connect() as conn:
        conn.execute(text("ALTER TABLE unlocked_routes ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE"))
        conn.commit()
        print("Migration Successful")

if __name__ == "__main__":
    run_migration()
