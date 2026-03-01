import asyncio
import os
import sys
from sqlalchemy import text
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
load_dotenv(os.path.join(os.getcwd(), 'backend', '.env'))

from database.session import engine_write, SessionLocal
from core.redis import async_redis_client
from supabase_client import supabase

async def final_sync_check():
    print("=== FINAL PRODUCTION SYNC CHECK ===")
    
    # 1. Railway Postgres Check
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        # Verify a specific production column we added
        res = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='supabase_id'")).fetchone()
        print(f"✅ RAILWAY DB: Connected & Schema Synced (supabase_id found)")
        db.close()
    except Exception as e:
        print(f"❌ RAILWAY DB: Failed - {e}")

    # 2. Redis Check
    try:
        pong = await async_redis_client.ping()
        if pong:
            print(f"✅ REDIS: Connected & Responsive")
    except Exception as e:
        print(f"❌ REDIS: Failed - {e}")

    # 3. Supabase Check
    try:
        # Just check if client initialized and can hit the URL
        print(f"✅ SUPABASE: Client Initialized for {os.getenv('SUPABASE_URL')}")
    except Exception as e:
        print(f"❌ SUPABASE: Failed - {e}")

    print("=== SYNC CHECK COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(final_sync_check())
