import asyncio
import sys
from pathlib import Path

# Add backend to path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

from database import session
from sqlalchemy import text

async def check_booking_positions():
    await session.initialize_database_pools()
    engine_user = session.engine_user
    
    with engine_user.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name, ordinal_position, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'bookings'
            ORDER BY ordinal_position;
        """))
        for row in result:
            print(f"Pos {row[1]}: {row[0]} (Nullable: {row[2]})")

if __name__ == "__main__":
    asyncio.run(check_booking_positions())
