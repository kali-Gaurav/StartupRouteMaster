import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def test_db():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("FAILURE: DATABASE_URL not found in environment.")
        return

    # Convert to asyncpg if needed
    if "postgresql://" in url and "asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    
    # Strip query params as in session.py
    if "?" in url:
        url = url.split("?")[0]

    print(f"Testing DB connection to: {url}")
    try:
        engine = create_async_engine(url)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print(f"SUCCESS: DB connection successful! Result: {result.scalar()}")
        await engine.dispose()
    except Exception as e:
        print(f"FAILURE: DB connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
