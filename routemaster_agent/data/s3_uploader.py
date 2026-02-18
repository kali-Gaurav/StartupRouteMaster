"""Simple S3 upload helper for dataset artifacts.

Usage:
  from routemaster_agent.data.s3_uploader import upload_directory_to_s3
  upload_directory_to_s3('datasets/phase2_ready', 'my-bucket', prefix='phase2/v1')

Requires `boto3` available in the environment.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional


def _boto3_client():
    try:
        import boto3
    except Exception as e:
        raise RuntimeError("boto3 is required to upload to S3 — install it in your environment") from e
    return boto3.client("s3")


def upload_directory_to_s3(local_dir: str | Path, bucket: str, prefix: Optional[str] = None):
    local_dir = Path(local_dir)
    if not local_dir.exists():
        raise FileNotFoundError(local_dir)

    prefix = (prefix.rstrip("/") + "/") if prefix else ""
    client = _boto3_client()

    for p in sorted(local_dir.rglob("*")):
        if p.is_file():
            key = prefix + str(p.relative_to(local_dir)).replace('\\', '/')
            client.upload_file(str(p), bucket, key)
    return True
