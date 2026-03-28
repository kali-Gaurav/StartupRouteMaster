import asyncio
from database.session import initialize_database_pools, SessionTransit
from sqlalchemy import text

async def list_tables():
    await initialize_database_pools()
    s = SessionTransit()
    res = s.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    print("Tables in Transit DB:")
    for r in res:
        print(f"  - {r[0]}")
    s.close()

if __name__ == "__main__":
    asyncio.run(list_tables())
