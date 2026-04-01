import sys
import os
import asyncio
sys.path.append(os.path.join(os.getcwd()))
from database.session import SessionTransit, initialize_database_pools
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.ERROR)

async def check_schema():
    await initialize_database_pools()
    s = SessionTransit()
    try:
        r = s.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'hub_connectivity_index'")).fetchall()
        print("Schema:", r)
        
        # Check if it has data
        count = s.execute(text("SELECT count(*) FROM hub_connectivity_index")).scalar()
        print("Count:", count)
        
        if count > 0:
            sample = s.execute(text("SELECT src_hub_id, dst_hub_id FROM hub_connectivity_index LIMIT 1")).fetchone()
            print("Sample Row IDS:", sample)
    except Exception as e:
        print("Error:", e)
    finally:
        s.close()

if __name__ == "__main__":
    asyncio.run(check_schema())
