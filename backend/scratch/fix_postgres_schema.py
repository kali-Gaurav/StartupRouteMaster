import asyncio
import sys
from pathlib import Path

# Add backend to path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

from database import session
from database.base import Base
from sqlalchemy import text, inspect

async def force_fix_postgres_schema():
    await session.initialize_database_pools()
    engine_user = session.engine_user
    
    print("Force recreating merchant_vpas table in Postgres...")
    
    try:
        from database.models import MerchantVPA
        
        with engine_user.connect() as conn:
            # Drop the table if it exists
            conn.execute(text("DROP TABLE IF EXISTS merchant_vpas CASCADE"))
            conn.commit()
            print("Dropped 'merchant_vpas' table.")
        
        # Now recreate
        Base.metadata.create_all(bind=engine_user)
        print("Recreated tables using metadata.create_all.")
        
        # Verify
        inspector = inspect(engine_user)
        if 'merchant_vpas' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('merchant_vpas')]
            print(f"New columns in Postgres 'merchant_vpas': {columns}")
            
            if 'id' in columns:
                with engine_user.connect() as conn:
                    conn.execute(text("INSERT INTO merchant_vpas (vpa, name, is_active, last_reset_at) VALUES ('test@vpa', 'Test VPA', true, now())"))
                    conn.commit()
                    print("✅ Successfully forced repair and populated 'merchant_vpas' in Postgres.")
            else:
                print("❌ 'id' column STILL MISSING! Model definition mismatch?")
        else:
            print("❌ FAILED to recreate 'merchant_vpas'.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(force_fix_postgres_schema())
