import asyncio
import os
import sys

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import init_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_init():
    logger.info("Initializing database schema on Railway PostgreSQL...")
    try:
        await init_db()
        logger.info("✓ Database schema initialization completed successfully!")
        return True
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_init())
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
