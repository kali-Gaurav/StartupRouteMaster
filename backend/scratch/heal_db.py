
import asyncio
import sys
import logging
from pathlib import Path
from sqlalchemy import text

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

import database.session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_healer")

async def heal_user_table():
    await database.session.initialize_database_pools()
    engine = database.session.async_engine_user
    
    # List of columns to add with their types for PostgreSQL
    # Using 'IF NOT EXISTS' equivalent logic for Postgres
    columns_to_add = [
        ("full_name", "VARCHAR(255)"),
        ("is_verified", "BOOLEAN DEFAULT FALSE"),
        ("verified_at", "TIMESTAMP"),
        ("last_active_at", "TIMESTAMP"),
        ("preferences", "JSONB"),
        ("telegram_id", "VARCHAR(255)"),
        ("telegram_link_token", "VARCHAR(255)"),
        ("telegram_link_expiry", "TIMESTAMP"),
        ("encrypted_irctc_creds", "TEXT"),
        ("creds_iv", "TEXT"),
        ("opt_in_persistent_creds", "BOOLEAN DEFAULT FALSE"),
        ("credit_balance", "INTEGER DEFAULT 0"),
        ("bonus_credit_balance", "INTEGER DEFAULT 0"),
        ("total_lifetime_credits", "INTEGER DEFAULT 0"),
        ("referral_code", "VARCHAR(50)"),
        ("referred_by_id", "INTEGER"),
        ("karma_score", "INTEGER DEFAULT 0"),
        ("referral_status", "VARCHAR(50)"),
        ("last_fingerprint", "VARCHAR(255)")
    ]
    
    async with engine.begin() as conn:
        logger.info("🛠 Healing 'users' table in Postgres...")
        
        # Check current columns to avoid 'already exists' errors
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users';"))
        existing_columns = {row[0] for row in result}
        
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                logger.info(f"➕ Adding column: {col_name} ({col_type})")
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};"))
                # Mark as added so we don't try again if script is re-run
                existing_columns.add(col_name)
            else:
                logger.info(f"✅ Column {col_name} already exists.")
                
        logger.info("🎉 'users' table healed successfully.")

if __name__ == "__main__":
    asyncio.run(heal_user_table())
