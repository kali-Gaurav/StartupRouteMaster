import asyncio
from database.session import SessionLocal, initialize_database_pools
from sqlalchemy import text

async def field_by_field():
    await initialize_database_pools()
    db = SessionLocal()
    uid = 'test_user_123'
    
    # Get columns
    cols = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND table_schema = 'public'")).fetchall()
    
    for (col,) in cols:
        try:
            res = db.execute(text(f"SELECT {col} FROM public.users WHERE id = :id"), {"id": uid}).fetchone()
            print(f"Column {col}: SUCCESS")
        except Exception as e:
            print(f"Column {col}: FAILED - {e}")
            db.rollback()
    db.close()

if __name__ == "__main__":
    asyncio.run(field_by_field())
