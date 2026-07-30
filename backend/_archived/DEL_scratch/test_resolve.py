import asyncio
import sqlite3
from database.session import SessionTransit
from utils.station_utils import resolve_stations

async def test():
    db = SessionTransit()
    try:
        src, dst = resolve_stations(db, "BCT", "NDLS")
        print(f"Source: {src.code if src else 'None'} (id={src.id if src else 'N/A'})")
        print(f"Dest: {dst.code if dst else 'None'} (id={dst.id if dst else 'N/A'})")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test())
