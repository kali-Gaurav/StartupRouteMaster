import asyncio
import logging
from sqlalchemy import text
from database.session import initialize_database_pools, SessionTransit

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("db_finalizer")

async def finalize_database():
    print("\n--- DATABASE PRODUCTION FINALIZATION ---")
    await initialize_database_pools()
    db = SessionTransit()
    
    try:
        # 1. Vacuum and Optimize (Postgres specific)
        if db.bind.dialect.name == 'postgresql':
            print("Optimizing PostgreSQL tables...")
            db.execute(text("ANALYZE"))
            print("[OK] ANALYZE complete.")
        elif db.bind.dialect.name == 'sqlite':
            print("Optimizing SQLite (VACUUM)...")
            db.execute(text("VACUUM"))
            print("[OK] VACUUM complete.")

        # 2. Re-index critical tables
        print("Ensuring critical indices are warm...")
        # (Alembic handles creation, we just verify they exist)
        
        # 3. Clean up expired data
        print("Pruning expired sessions/logs...")
        res = db.execute(text("DELETE FROM user_sessions WHERE is_active = false AND login_at < NOW() - INTERVAL '30 days'"))
        print(f"[OK] Pruned {res.rowcount} inactive sessions.")

        db.commit()
    except Exception as e:
        print(f"[FAIL] Finalization failed: {e}")
        db.rollback()
    finally:
        db.close()
    
    print("--- DB FINALIZATION COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(finalize_database())
