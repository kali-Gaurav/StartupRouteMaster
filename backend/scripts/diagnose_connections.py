import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import redis.asyncio as redis
import psycopg2
from supabase import create_client, Client

# Setup logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("diagnose-connections")

def log_error(msg):
    # Remove emojis for Windows compatibility
    msg = msg.replace('✅', '[OK]').replace('❌', '[FAIL]').replace('⚠️', '[WARN]').replace('✨', '[SUCCESS]')
    with open("backend/scripts/diag_error.log", "a") as f:
        f.write(msg + "\n")
    logger.error(msg)

async def test_redis():
    url = os.getenv("REDIS_URL")
    if not url:
        log_error("[FAIL] REDIS_URL not found")
        return False
    
    logger.info(f"Testing Redis: {url.split('@')[-1]}")
    try:
        r = redis.Redis.from_url(url, ssl_cert_reqs=None, socket_connect_timeout=5.0)
        await r.ping()
        logger.info("[OK] Redis Connection Successful")
        await r.close()
        return True
    except Exception as e:
        log_error(f"[FAIL] Redis Connection Failed: {e}")
        return False

def test_supabase_pg_variation(host, user, password, dbname, port, name):
    logger.info(f"Testing {name}: {host}:{port} with user {user}")
    try:
        conn = psycopg2.connect(
            host=host,
            user=user,
            password=password,
            dbname=dbname,
            port=port,
            connect_timeout=5
        )
        conn.close()
        logger.info(f"[OK] {name} Successful")
        return True
    except Exception as e:
        log_error(f"[FAIL] {name} Failed: {e}")
        return False

def test_supabase_api():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        log_error("[FAIL] Supabase API credentials missing")
        return False
    
    logger.info(f"Testing Supabase API: {url}")
    try:
        supabase: Client = create_client(url, key)
        logger.info("[OK] Supabase API Client Initialized")
        return True
    except Exception as e:
        log_error(f"[FAIL] Supabase API Connection Failed: {e}")
        return False

async def main():
    # Load .env from backend root
    root_dir = Path(__file__).resolve().parent.parent
    env_path = root_dir / '.env'
    logger.info(f"Loading environment from {env_path}")
    load_dotenv(dotenv_path=env_path, override=True)
    
    # 1. Test Redis
    r_res = await test_redis()
    
    # 2. Test Supabase PG Variations
    password = os.getenv("POSTGRES_PASSWORD")
    dbname = os.getenv("POSTGRES_DATABASE", "postgres")
    
    # Variation 1: Direct host (original .env)
    pg1 = test_supabase_pg_variation(
        "db.bkzrxgtsfovctfviqkuh.supabase.co", "postgres", password, dbname, 5432, "Direct Host"
    )
    
    # Variation 2: Pooler host with ref user (Prisma style)
    pg2 = test_supabase_pg_variation(
        "aws-1-ap-south-1.pooler.supabase.com", "postgres.bkzrxgtsfovctfviqkuh", password, dbname, 5432, "Pooler Host (5432)"
    )
    
    # Variation 3: Pooler host with ref user (Port 6543)
    pg3 = test_supabase_pg_variation(
        "aws-1-ap-south-1.pooler.supabase.com", "postgres.bkzrxgtsfovctfviqkuh", password, dbname, 6543, "Pooler Host (6543)"
    )
    
    # 3. Test Supabase API
    api_res = test_supabase_api()
    
    if r_res and (pg1 or pg2 or pg3) and api_res:
        logger.info("\n[SUCCESS] ALL CONNECTIONS VERIFIED SUCCESSFULLY")
    else:
        logger.error("\n[WARN] SOME CONNECTIONS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
