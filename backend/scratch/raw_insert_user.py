import asyncio
from database.session import SessionLocal, initialize_database_pools
from sqlalchemy import text

async def raw_insert():
    await initialize_database_pools()
    db = SessionLocal()
    try:
        db.execute(text("INSERT INTO public.users (id, full_name, password_hash) VALUES ('test_v_raw', 'Test', 'H')"))
        db.commit()
        print("Raw Insert Success")
    except Exception as e:
        print(f"Raw Insert Failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(raw_insert())
