import asyncio
import sys
from pathlib import Path

# Add backend to path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

from database.session import SessionTransit, initialize_database_pools
from sqlalchemy import text, inspect

async def check_all_tables():
    await initialize_database_pools()
    db = SessionTransit()
    try:
        inspector = inspect(db.get_bind())
        tables = inspector.get_table_names()
        print(f"Tables in DB: {tables}")
        
        if 'merchant_vpas' in tables:
            columns = inspector.get_columns('merchant_vpas')
            print(f"Columns in 'merchant_vpas': {[c['name'] for c in columns]}")
        else:
            print("'merchant_vpas' table NOT FOUND.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(check_all_tables())
