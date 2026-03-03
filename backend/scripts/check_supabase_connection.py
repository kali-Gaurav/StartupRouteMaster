import os
import sys
import asyncio
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from supabase import create_client
import redis.asyncio as aioredis
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("check_supabase")

# Add backend to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the monkeypatch from supabase_client to avoid proxy issues
try:
    import supabase_client
    logger.info("✅ Imported supabase_client (applying monkeypatch).")
except Exception as e:
    logger.warning(f"⚠️ Could not import supabase_client: {e}")

from database.config import Config

async def test_postgres():
    logger.info("Testing Postgres Connection via SQLAlchemy...")
    try:
        db_url = Config.DATABASE_URL
        if not db_url:
            logger.error("❌ DATABASE_URL is empty in Config.")
            return
            
        # Log non-sensitive parts of the URL
        from urllib.parse import urlparse
        try:
            parsed = urlparse(db_url)
            logger.info(f"DB URL: {parsed.scheme}://****@{parsed.hostname}:{parsed.port}/{parsed.path.strip('/')}")
        except:
            logger.warning("Could not parse DATABASE_URL correctly.")

        engine = create_engine(
            db_url,
            echo=False
        )
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            logger.info(f"✅ Postgres Connection Successful! Version: {version}")
            
            # Check extensions
            result = conn.execute(text("SELECT * FROM pg_extension WHERE extname = 'pg_trgm';"))
            if result.fetchone():
                logger.info("✅ pg_trgm extension found.")
            else:
                logger.warning("❌ pg_trgm extension NOT found.")
                
            # Check for profiles table
            result = conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_name = 'profiles';"))
            if result.fetchone()[0] > 0:
                logger.info("✅ 'profiles' table exists.")
            else:
                logger.warning("❌ 'profiles' table NOT found.")
                
    except Exception as e:
        logger.error(f"❌ Postgres Connection Failed: {e}")

async def test_supabase_rest():
    logger.info("Testing Supabase REST API Connection...")
    try:
        url = Config.SUPABASE_URL
        key = Config.SUPABASE_SERVICE_KEY or Config.SUPABASE_KEY
        
        if not url or not key:
            logger.error("❌ SUPABASE_URL or SUPABASE_KEY missing in Config.")
            return

        supabase = create_client(url, key)
        # Try to list profiles (using service key if possible)
        try:
            resp = supabase.table("profiles").select("*").limit(1).execute()
            logger.info("✅ Supabase REST API Connection Successful!")
            if hasattr(resp, "data"):
                logger.info(f"✅ Data fetched: {len(resp.data)} rows.")
        except Exception as api_err:
            logger.error(f"❌ Supabase REST API query failed: {api_err}")
            
    except Exception as e:
        logger.error(f"❌ Supabase REST API Client Initialization Failed: {e}")

async def test_redis():
    logger.info("Testing Redis Connection...")
    try:
        redis_url = Config.REDIS_URL
        if not redis_url:
            logger.warning("Redis URL not set in Config.")
            return
            
        r = aioredis.from_url(redis_url, encoding="utf8", decode_responses=True)
        ping = await r.ping()
        if ping:
            logger.info("✅ Redis Connection Successful!")
    except Exception as e:
        logger.error(f"❌ Redis Connection Failed: {e}")

async def main():
    logger.info("Starting Production Readiness Check...")
    await test_postgres()
    await test_supabase_rest()
    await test_redis()
    logger.info("Check complete.")

if __name__ == "__main__":
    asyncio.run(main())
