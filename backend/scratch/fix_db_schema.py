import asyncio
import sys
from pathlib import Path

# Add backend to path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

from database.session import init_db, SessionTransit, initialize_database_pools
from sqlalchemy import text

async def run_init_db():
    print("Initializing database schema...")
    await init_db()
    
    # After init, try to insert the test VPA
    await initialize_database_pools()
    db = SessionTransit()
    try:
        print("Inserting test VPA into 'merchant_vpas'...")
        # Check if table exists now
        from sqlalchemy import inspect
        inspector = inspect(db.get_bind())
        if 'merchant_vpas' in inspector.get_table_names():
            db.execute(text("INSERT INTO merchant_vpas (vpa, name, is_active) VALUES ('test@vpa', 'Test VPA', true)"))
            db.commit()
            print("✅ Successfully created and populated 'merchant_vpas'.")
        else:
            print("❌ 'merchant_vpas' table still NOT FOUND after init_db().")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_init_db())
