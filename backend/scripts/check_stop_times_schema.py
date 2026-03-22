import sys
import os
import asyncio
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from database.session import SessionTransit
from core.container import container

async def check_schema():
    await container.get("db")
    db = SessionTransit()
    try:
        print("Schema for 'stop_times':")
        res = db.execute(text("PRAGMA table_info(stop_times)")).fetchall()
        for r in res:
            print(r)
            
        print("\nSchema for 'calendar':")
        res = db.execute(text("PRAGMA table_info(calendar)")).fetchall()
        for r in res:
            print(r)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(check_schema())
