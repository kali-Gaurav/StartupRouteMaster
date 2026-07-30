import asyncio
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import initialize_database_pools, SessionUser
from sqlalchemy import inspect

async def main():
    logging.basicConfig(level=logging.INFO)
    await initialize_database_pools()
    
    db = SessionUser()
    try:
        inspector = inspect(db.get_bind())
        tables = inspector.get_table_names()
        print("Existing Tables:")
        for table in sorted(tables):
            print(f" - {table}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
