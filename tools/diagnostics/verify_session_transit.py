import sys
import os
from pathlib import Path

# Add backend to sys.path
root = Path(__file__).resolve().parent
sys.path.append(str(root / "backend"))

from backend.database.session import initialize_database_pools, SessionTransit
from sqlalchemy import text

async def test_connection():
    await initialize_database_pools()
    session = SessionTransit()
    try:
        # Check tables in the session's database
        res = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        tables = [r[0] for r in res]
        print(f"Tables in SessionTransit: {tables}")
        
        if 'hub_connectivity_index' in tables:
            count = session.execute(text("SELECT count(*) FROM hub_connectivity_index")).scalar()
            print(f"hub_connectivity_index row count: {count}")
        else:
            print("hub_connectivity_index NOT FOUND in SessionTransit!")
            
        if 'stops' in tables:
            count = session.execute(text("SELECT count(*) FROM stops")).scalar()
            print(f"stops row count: {count}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_connection())
