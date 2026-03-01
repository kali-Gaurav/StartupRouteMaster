import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from database.session import engine_write
from sqlalchemy import text

def run_migration():
    with engine_write.connect() as conn:
        try:
            # For Postgres: Drop the restrictive foreign key constraints
            conn.execute(text("ALTER TABLE unlocked_routes DROP CONSTRAINT IF EXISTS unlocked_routes_route_id_fkey"))
            conn.execute(text("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_route_id_fkey"))
            conn.commit()
            print("FK constraints dropped successfully (Postgres)")
        except Exception as e:
            print(f"Note: This might be SQLite or constraints don't exist: {e}")
            conn.rollback()

if __name__ == "__main__":
    run_migration()
