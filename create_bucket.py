import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from utils.storage import storage

try:
    print(f"Attempting to create/verify bucket: {storage.bucket_name}")
    try:
        storage.s3_client.head_bucket(Bucket=storage.bucket_name)
        print(f"Bucket {storage.bucket_name} already exists.")
    except:
        storage.s3_client.create_bucket(Bucket=storage.bucket_name)
        print(f"Bucket {storage.bucket_name} created successfully!")
except Exception as e:
    print(f"Failed to create/verify bucket: {e}")
