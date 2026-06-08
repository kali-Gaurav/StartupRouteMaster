import asyncio
import logging
from datetime import datetime
from sqlalchemy import text, select
from database.session import initialize_database_pools, SessionTransit
from database.models import User
from services.cache_service import cache_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("identity_audit")

async def run_identity_audit():
    print("\n--- IDENTITY & TELEGRAM LINKING AUDIT ---")
    await initialize_database_pools()
    db = SessionTransit()
    
    try:
        # 1. Check for Telegram Linking Health
        total_users = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        linked_users = db.execute(text("SELECT COUNT(*) FROM users WHERE telegram_id IS NOT NULL")).scalar()
        pending_links = db.execute(text("SELECT COUNT(*) FROM users WHERE telegram_link_token IS NOT NULL AND telegram_link_expiry > NOW()")).scalar()
        expired_links = db.execute(text("SELECT COUNT(*) FROM users WHERE telegram_link_token IS NOT NULL AND telegram_link_expiry <= NOW()")).scalar()

        print(f"Total Users: {total_users}")
        print(f"Successfully Linked Telegram Users: {linked_users}")
        print(f"Pending Active Links: {pending_links}")
        print(f"Expired (Unclaimed) Links: {expired_links}")

        # 2. Check for Duplicate Telegram IDs (Security Audit)
        dupes = db.execute(text("""
            SELECT telegram_id, COUNT(*) 
            FROM users 
            WHERE telegram_id IS NOT NULL 
            GROUP BY telegram_id 
            HAVING COUNT(*) > 1
        """)).fetchall()
        
        if dupes:
            print(f"[CRITICAL] Found {len(dupes)} duplicate Telegram IDs! Potential account takeover risk.")
            for d in dupes:
                print(f"  - Telegram ID {d[0]} is linked to {d[1]} accounts.")
        else:
            print("[OK] No duplicate Telegram IDs found.")

        # 3. Cache Integrity Check (Task 3.1 Session matching)
        if cache_service.is_available():
            # Check for dangling link tokens in Redis if applicable
            # (Assuming tokens are primarily in DB as per models.py)
            print("[OK] Redis Session Cache is reachable.")
        else:
            print("[WARN] Redis is unavailable; cannot verify active session-based linking tokens.")

    except Exception as e:
        logger.error(f"Identity audit failed: {e}")
    finally:
        db.close()
    print("--- IDENTITY AUDIT COMPLETE ---\n")

if __name__ == "__main__":
    asyncio.run(run_identity_audit())
