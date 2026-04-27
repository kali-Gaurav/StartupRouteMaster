import asyncio
import sys
from pathlib import Path

# Add backend to path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

from database import session
from sqlalchemy import inspect

async def check_booking_columns():
    await session.initialize_database_pools()
    engine_user = session.engine_user
    
    inspector = inspect(engine_user)
    columns = inspector.get_columns('bookings')
    print(f"Columns in 'bookings': {[c['name'] for c in columns]}")
    
    # Check nullability
    for c in columns:
        print(f"Column: {c['name']}, Nullable: {c['nullable']}")

if __name__ == "__main__":
    asyncio.run(check_booking_columns())
