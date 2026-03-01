import asyncio
import os
import sys
from sqlalchemy import text

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_railway_conn():
    logger.info("Testing connection to Railway PostgreSQL...")
    db = SessionLocal()
    try:
        # Simple query to check connectivity
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            logger.info("✓ Railway PostgreSQL connection successful!")
            return True
        else:
            logger.error("✗ Railway PostgreSQL returned unexpected result.")
            return False
    except Exception as e:
        logger.error(f"✗ Railway PostgreSQL connection failed: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = asyncio.run(test_railway_conn())
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
