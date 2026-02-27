
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_path))

# Force OFFLINE_MODE to False for this test
os.environ["OFFLINE_MODE"] = "false"

from database.config import Config
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_supabase")

def test_connection():
    logger.info(f"Checking configuration...")
    logger.info(f"OFFLINE_MODE: {Config.OFFLINE_MODE}")
    
    url = os.getenv("DATABASE_URL")
    if not url:
        logger.error("❌ DATABASE_URL not found in environment!")
        return

    logger.info(f"Attempting to connect to Supabase Postgres...")
    # Mask password for logging
    masked_url = url.split("@")[-1] if "@" in url else url
    logger.info(f"Connecting to: ...@{masked_url}")

    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()
            logger.info(f"✅ SUCCESS! Connected to: {version[0]}")
            
            # Check for a specific table
            result = conn.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public' LIMIT 5;"))
            tables = result.fetchall()
            logger.info(f"Public tables found: {[t[0] for t in tables]}")
            
    except Exception as e:
        logger.error(f"❌ CONNECTION FAILED: {e}")
        logger.info("\nTroubleshooting Tips:")
        logger.info("1. Check if your IP is whitelisted in Supabase (Settings -> Database -> Network Restrictions)")
        logger.info("2. Ensure you are using the Session Pooler port (6543) if you have many connections.")
        logger.info("3. Verify the password in your DATABASE_URL.")

if __name__ == "__main__":
    test_connection()
