
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.utils.storage import storage

async def verify():
    print("🔍 [VERIFY] Listing Cloudflare R2 'backups/' objects...")
    objects = storage.list_objects(prefix="backups/")
    for obj in objects:
        print(f"📄 {obj['Key']} ({obj['Size'] / 1024 / 1024:.2f} MB)")

if __name__ == "__main__":
    asyncio.run(verify())
