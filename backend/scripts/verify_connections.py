import redis
import os
from sqlalchemy import create_engine, text
from database.config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_supabase():
    logger.info("Testing Supabase connection...")
    try:
        engine = create_engine(Config.DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT NOW();"))
            row = result.fetchone()
            logger.info(f"✅ Connected to Supabase! Current time: {row[0]}")
            return True
    except Exception as e:
        logger.error(f"❌ Failed to connect to Supabase: {e}")
        return False

def test_redis():
    logger.info("Testing Redis connection...")
    try:
        r = redis.from_url(Config.REDIS_URL, decode_responses=True, ssl_cert_reqs=None)
        r.ping()
        logger.info("✅ Connected to Redis!")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        return False

if __name__ == "__main__":
    s_ok = test_supabase()
    r_ok = test_redis()
    
    if s_ok and r_ok:
        logger.info("🚀 ALL CONNECTIONS STABLE AND VERIFIED!")
    else:
        logger.error("⚠️ System verification failed.")
        exit(1)
