import asyncio
from database.session import SessionLocal, initialize_database_pools
from sqlalchemy import text

async def all_at_once():
    await initialize_database_pools()
    db = SessionLocal()
    uid = 'test_user_123'
    
    try:
        res = db.execute(text(f"SELECT * FROM public.users WHERE id = :id"), {"id": uid}).fetchone()
        print(f"Select * SUCCESS: {res}")
    except Exception as e:
        print(f"Select * FAILED - {e}")
    db.close()

if __name__ == "__main__":
    asyncio.run(all_at_once())
