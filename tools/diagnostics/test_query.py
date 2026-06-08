import asyncio
import sys
sys.path.append('backend')
from database.session import SessionLocal, initialize_database_pools
from database.models import Stop
async def main():
    await initialize_database_pools()
    db = SessionLocal()
    try:
        print(db.query(Stop).first())
    except Exception as e:
        print(repr(e))
asyncio.run(main())
