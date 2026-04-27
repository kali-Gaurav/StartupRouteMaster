import asyncio
import sys
from pathlib import Path

# Add backend to path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

from database import session
from database.base import Base
from sqlalchemy import text, inspect

async def force_sync_bookings_schema():
    await session.initialize_database_pools()
    engine_user = session.engine_user
    
    print("Force recreating bookings table in Postgres to ensure schema alignment...")
    
    try:
        from database.models import Booking
        
        with engine_user.connect() as conn:
            # We need to be careful about foreign keys if any tables depend on bookings
            # But usually it's the other way around.
            conn.execute(text("DROP TABLE IF EXISTS bookings CASCADE"))
            conn.commit()
            print("Dropped 'bookings' table.")
        
        # Now recreate
        Base.metadata.create_all(bind=engine_user)
        print("Recreated tables using metadata.create_all.")
        
        # Verify
        inspector = inspect(engine_user)
        if 'bookings' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('bookings')]
            print(f"New columns in Postgres 'bookings': {columns}")
            print("✅ Successfully forced repair of 'bookings' table.")
        else:
            print("❌ FAILED to recreate 'bookings'.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(force_sync_bookings_schema())
