
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_path))

from sqlalchemy import create_engine, text
from database.config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_extensions")

def init_extensions():
    url = Config.DATABASE_URL
    if not url or Config.OFFLINE_MODE:
        logger.error("OFFLINE_MODE is enabled or DATABASE_URL is missing. Skipping extension initialization.")
        return

    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            # We need to use a transaction for some extensions
            with conn.begin():
                logger.info("Enabling pg_trgm extension for fuzzy search...")
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
                
                # Check for postgis if you plan to use geometry (optional, might need superuser)
                # logger.info("Enabling postgis extension for geographical queries...")
                # conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                
            logger.info("✅ Extensions initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize extensions: {e}")
        logger.info("Note: You might need to enable extensions manually in the Supabase Dashboard (Database -> Extensions) if the user lacks permissions.")

if __name__ == "__main__":
    init_extensions()
