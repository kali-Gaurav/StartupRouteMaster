import asyncio
from sqlalchemy import text
from database.session import initialize_database_pools

async def check_columns():
    await initialize_database_pools()
    from database.session import async_engine_user
    async with async_engine_user.connect() as conn:
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'route_search_logs'"))
        columns = [row[0] for row in result]
        print(f"Columns in route_search_logs: {columns}")

if __name__ == "__main__":
    asyncio.run(check_columns())
