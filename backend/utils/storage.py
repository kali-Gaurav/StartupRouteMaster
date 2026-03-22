import boto3
from botocore.config import Config as BotoConfig
from database.config import Config
import logging
import hashlib
from typing import Optional, BinaryIO, Dict, Any
from pathlib import Path

logger = logging.getLogger("routemaster.storage")

class R2Storage:
    """
    Cloudflare R2 Storage client using S3-compatible API.
    """
    def __init__(self):
        self.account_id = Config._get_env("CLOUDFLARE_R2_ACCOUNT_ID")
        self.access_key_id = Config._get_env("CLOUDFLARE_R2_ACCESS_KEY_ID")
        self.secret_access_key = Config._get_env("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
        self.endpoint_url = Config._get_env("CLOUDFLARE_R2_S3_API")
        self.bucket_name = Config._get_env("CLOUDFLARE_R2_BUCKET_NAME", "routemaster-storage")

        if not all([self.account_id, self.access_key_id, self.secret_access_key, self.endpoint_url]):
            logger.warning(f"⚠️ Cloudflare R2 credentials not fully configured. Missing: {[k for k in ['ACCOUNT_ID', 'ACCESS_KEY', 'SECRET_KEY', 'S3_API'] if not getattr(self, k.lower().replace('s3_api', 'endpoint_url'))]}")

        self.s3_client = boto3.client(
            service_name='s3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name='auto',  # R2 uses 'auto'
            config=BotoConfig(s3={'addressing_style': 'path'})
        )

    @staticmethod
    def calculate_sha256(file_path: str | Path) -> str:
        """Calculate SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def upload_file(self, file_path: str | Path, object_name: Optional[str] = None, metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload a file to R2 bucket with optional metadata."""
        file_path = Path(file_path)
        if object_name is None:
            object_name = file_path.name

        extra_args = {}
        if metadata:
            extra_args['Metadata'] = metadata

        try:
            self.s3_client.upload_file(str(file_path), self.bucket_name, object_name, ExtraArgs=extra_args)
            logger.info(f"Successfully uploaded {file_path} to {self.bucket_name}/{object_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error uploading file to R2: {e}", exc_info=True)
            return False

    def get_object_metadata(self, object_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata for an object."""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=object_name)
            return response.get('Metadata', {})
        except Exception as e:
            logger.debug(f"Metadata not found for {object_name}: {e}")
            return None

    def upload_fileobj(self, fileobj: BinaryIO, object_name: str) -> bool:
        """Upload a file-like object to R2 bucket."""
        try:
            self.s3_client.upload_fileobj(fileobj, self.bucket_name, object_name)
            logger.info(f"Successfully uploaded object to {self.bucket_name}/{object_name}")
            return True
        except Exception as e:
            logger.error(f"Error uploading fileobj to R2: {e}")
            return False

    def download_file(self, object_name: str, file_path: str | Path) -> bool:
        """Download an object from R2 bucket."""
        try:
            self.s3_client.download_file(self.bucket_name, object_name, str(file_path))
            logger.info(f"Successfully downloaded {object_name} from {self.bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Error downloading file from R2: {e}")
            return False

    def delete_object(self, object_name: str) -> bool:
        """Delete an object from R2 bucket."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            logger.info(f"Successfully deleted {object_name} from {self.bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting object from R2: {e}")
            return False

    def list_objects(self, prefix: str = ""):
        """List objects in R2 bucket."""
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            return response.get('Contents', [])
        except Exception as e:
            logger.error(f"Error listing objects from R2: {e}")
            return []

# Singleton instance
storage = R2Storage()
