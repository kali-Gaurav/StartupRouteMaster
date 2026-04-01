import asyncio
import os
import sys
import logging

# Add project root to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from dotenv import load_dotenv
load_dotenv('backend/.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("r2.check")

async def check_r2_sync():
    try:
        from services.storage_sync import r2_sync_manager
        from utils.storage import storage as r2_storage
        
        db_path = "database/transit_graph.db"
        logger.info(f"🔍 Checking R2 Sync Status for {db_path}...")
        
        # 1. Probing R2 Bucket
        bucket = os.getenv("CLOUDFLARE_R2_BUCKET_NAME")
        logger.info(f"☁️ R2 Bucket: {bucket}")
        
        # 2. Check Remote Metadata
        object_name = f"backups/{db_path.replace('/', '_')}.zst"
        metadata = r2_storage.get_object_metadata(object_name)
        
        if metadata:
            size_mb = metadata.get('size', 0) / (1024 * 1024)
            logger.info(f"✅ Remote Backup Found: {object_name} ({size_mb:.2f} MB)")
            logger.info(f"📅 Last Modified: {metadata.get('last_modified')}")
        else:
            logger.warning(f"⚠️ No remote backup found for {db_path} in R2.")

        # 3. Check Local Database
        local_path = os.path.join("backend", db_path)
        if os.path.exists(local_path):
            local_size = os.path.getsize(local_path) / (1024 * 1024)
            logger.info(f"📂 Local DB Found: {local_path} ({local_size:.2f} MB)")
        else:
            logger.error(f"❌ Local DB Not Found: {local_path}")

        return True
    except Exception as e:
        logger.error(f"❌ R2 Check Failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(check_r2_sync())
