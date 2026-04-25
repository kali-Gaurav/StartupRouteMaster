
import asyncio
import sys
from pathlib import Path
from sqlalchemy import inspect, text

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

import database.session

async def inspect_users():
    await database.session.initialize_database_pools()
    # Access the global engine_user from the session module
    engine = database.session.engine_user
    if engine is None:
        print("❌ engine_user is still None after initialization!")
        return
        
    async with database.session.async_engine_user.connect() as conn:
        # Get columns of 'users' table
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users';"))
        columns = [row[0] for row in result]
        print(f"Current columns in 'users' table: {columns}")

if __name__ == "__main__":
    asyncio.run(inspect_users())
