from sqlalchemy import text
import sys
import os
import asyncio

sys.path.append(os.path.join(os.getcwd(), 'backend'))
from core.container import container
from database.session import SessionTransit as SessionLocal

async def check():
    await container.get('db')
    db = SessionLocal()
    # NDLS
    ndls = db.execute(text("SELECT id, code FROM stops WHERE id=5533")).fetchone()
    print(f"ID 5533: Code='{ndls[1]}'")
    # MMCT
    mmct = db.execute(text("SELECT id, code FROM stops WHERE id=5080")).fetchone()
    print(f"ID 5080: Code='{mmct[1]}'")
    
    # Check what is in the bin table
    bin_codes = db.execute(text("SELECT station_code FROM station_transit_index_bin")).fetchall()
    codes = [r[0] for r in bin_codes]
    print(f"Is NDLS in bin? {'NDLS' in codes}")
    print(f"Is MMCT in bin? {'MMCT' in codes}")

if __name__ == "__main__":
    asyncio.run(check())
