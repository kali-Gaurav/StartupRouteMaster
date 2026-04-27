
import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from database import session
from database.base import UserBase
from database import models
from database import algorithm_models

async def init_tables():
    await session.initialize_database_pools()
    print("Initializing User Database tables (Supabase)...")
    
    # Get sorted tables by dependency
    tables = UserBase.metadata.sorted_tables
    
    for table in tables:
        # Create a new transaction for each table
        async with session.async_engine_user.begin() as conn:
            try:
                print(f"Checking table {table.name}...")
                await conn.run_sync(table.create)
                print(f"Created table {table.name}.")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"Table {table.name} already exists.")
                else:
                    print(f"Error creating table {table.name}: {e}")
    print("Done.")

if __name__ == "__main__":
    asyncio.run(init_tables())
