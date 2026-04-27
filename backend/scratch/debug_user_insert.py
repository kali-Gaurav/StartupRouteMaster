import asyncio
from database.session import SessionLocal, initialize_database_pools
from database.models import User
from sqlalchemy import text

async def debug_user_insert():
    await initialize_database_pools()
    db = SessionLocal()
    try:
        # Try to insert a minimal user
        import uuid
        uid = str(uuid.uuid4())[:36]
        user = User(id=uid, full_name="Debug User")
        db.add(user)
        db.commit()
        print(f"Successfully inserted user with ID: {uid}")
    except Exception as e:
        print(f"Insert failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(debug_user_insert())
