import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("nexus.r2")


class R2SyncService:
    """
    [Task 142] Cloudflare R2 Synchronization Service.
    Handles uploading transit database and snapshots for production distribution.

    Uses LAZY INITIALIZATION — the boto3 client is only created on first use.
    If R2 credentials are missing, all methods degrade gracefully (log + return False).
    """

    def __init__(self):
        self.account_id = os.getenv("CLOUDFLARE_R2_ACCOUNT_ID")
        self.endpoint_url = os.getenv("CLOUDFLARE_R2_S3_API")
        self.access_key = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID")
        self.secret_key = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "routemaster-storage")
        self._s3 = None  # Lazy: do NOT create client here to avoid import-time crashes

        if not all([self.endpoint_url, self.access_key, self.secret_key]):
            logger.warning(
                "⚠️  R2 credentials incomplete — R2SyncService running in DISABLED mode. "
                "Set CLOUDFLARE_R2_S3_API, CLOUDFLARE_R2_ACCESS_KEY_ID, "
                "CLOUDFLARE_R2_SECRET_ACCESS_KEY to enable."
            )

    @property
    def s3(self):
        """Lazy-initialize the boto3 S3 client only when first needed."""
        if self._s3 is None:
            if not all([self.endpoint_url, self.access_key, self.secret_key]):
                return None
            try:
                import boto3
                from botocore.config import Config
                self._s3 = boto3.client(
                    service_name="s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    config=Config(signature_version="s3v4"),
                )
                logger.info("✅ R2 boto3 client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to create R2 boto3 client: {e}")
                return None
        return self._s3

    def is_available(self) -> bool:
        """Return True if R2 is properly configured and client can be created."""
        return self.s3 is not None

    async def upload_transit_db(self, db_path: str = "database/transit_graph.db") -> bool:
        """Upload the core transit graph database."""
        if not self.is_available():
            logger.warning("R2 not available — skipping transit DB upload.")
            return False

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
                CopySource={"Bucket": self.bucket_name, "Key": dest_key},
                Key="db/transit_graph_latest.db",
            )
            logger.info("✅ Transit DB Uploaded and 'latest' pointer updated.")
            return True
        except Exception as e:
            logger.error(f"R2 Sync Failed: {e}")
            return False

    async def upload_latest_snapshot(self) -> bool:
        """Find and upload the latest .pkl snapshot."""
        if not self.is_available():
            logger.warning("R2 not available — skipping snapshot upload.")
            return False

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

    def health_check(self) -> dict:
        """Return R2 service health status."""
        return {
            "status": "available" if self.is_available() else "disabled",
            "bucket": self.bucket_name if self.is_available() else None,
            "endpoint": self.endpoint_url if self.is_available() else None,
        }


# Global singleton — safe to import at module level; no credentials required at init time
r2_sync = R2SyncService()
