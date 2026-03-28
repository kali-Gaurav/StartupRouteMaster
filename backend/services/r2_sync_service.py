import os
import boto3
import logging
from botocore.config import Config
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("nexus.r2")

class R2SyncService:
    """
    [Task 142] Cloudflare R2 Synchronization Service.
    Handles uploading transit database and snapshots for production distribution.
    """
    def __init__(self):
        self.account_id = os.getenv("CLOUDFLARE_R2_ACCOUNT_ID")
        self.endpoint_url = os.getenv("CLOUDFLARE_R2_S3_API")
        self.access_key = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID")
        self.secret_key = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "routemaster-storage")

        self.s3 = boto3.client(
            service_name='s3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version='s3v4')
        )

    async def upload_transit_db(self, db_path: str = "database/transit_graph.db"):
        """Upload the core transit graph database."""
        if not os.path.exists(db_path):
            logger.error(f"Transit DB not found at {db_path}")
            return False
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            dest_key = f"db/transit_graph_v3_{timestamp}.db"
            
            logger.info(f"Uploading Transit DB to R2: {dest_key}")
            self.s3.upload_file(db_path, self.bucket_name, dest_key)
            
            # Point 'latest' pointer
            self.s3.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': dest_key},
                Key="db/transit_graph_latest.db"
            )
            logger.info("✅ Transit DB Uploaded and 'latest' pointer updated.")
            return True
        except Exception as e:
            logger.error(f"R2 Sync Failed: {e}")
            return False

    async def upload_latest_snapshot(self):
        """Find and upload the latest .pkl snapshot."""
        snapshot_dir = "snapshots"
        if not os.path.exists(snapshot_dir):
            return False
            
        files = sorted([f for f in os.listdir(snapshot_dir) if f.endswith(".pkl")])
        if not files:
            logger.warning("No snapshots found to upload.")
            return False
            
        latest_file = files[-1]
        local_path = os.path.join(snapshot_dir, latest_file)
        
        try:
            dest_key = f"snapshots/{latest_file}"
            logger.info(f"Uploading Snapshot to R2: {dest_key}")
            self.s3.upload_file(local_path, self.bucket_name, dest_key)
            logger.info(f"✅ Snapshot {latest_file} uploaded to R2.")
            return True
        except Exception as e:
            logger.error(f"Snapshot R2 Sync Failed: {e}")
            return False

r2_sync = R2SyncService()
