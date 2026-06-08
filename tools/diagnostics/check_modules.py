import sys
import os
from pathlib import Path

# Add backend to sys.path
root = Path(__file__).resolve().parent
sys.path.append(str(root / "backend"))

import backend.database.session as bds
import database.session as ds

print(f"bds id: {id(bds)}")
print(f"ds id: {id(ds)}")
print(f"Same? {bds is ds}")

async def check():
    await bds.initialize_database_pools()
    print(f"bds initialized: {bds._pools_initialized}")
    print(f"ds initialized: {ds._pools_initialized}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(check())
