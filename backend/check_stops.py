import asyncio
from database.session import SessionTransit, initialize_database_pools
from sqlalchemy import text

async def check():
    await initialize_database_pools()
    s = SessionTransit()
    res = s.execute(text("SELECT code, name FROM stops ORDER BY id LIMIT 20")).fetchall()
    print("Available Station Codes:")
    for r in res:
        print(f"  - {r[0]} ({r[1]})")
    s.close()

if __name__ == "__main__":
    asyncio.run(check())
