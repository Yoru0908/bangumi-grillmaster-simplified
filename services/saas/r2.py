"""R2 presigned upload support using boto3 S3-compatible API."""

import uuid
from datetime import datetime, timezone

import boto3
from botocore.client import Config as BotoConfig

from settings import settings


def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=BotoConfig(
            signature_version="s3v4",
            region_name="auto",
        ),
    )


def generate_presigned_upload(filename: str) -> dict:
    """Generate a presigned URL for direct R2 upload."""
    key = f"uploads/{uuid.uuid4().hex}_{filename}"
    client = _r2_client()
    url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket,
            "Key": key,
            # Don't set ContentType — let the client decide, and don't include it in signature
        },
        ExpiresIn=3600,  # 1 hour
    )
    return {"key": key, "upload_url": url}


def download_from_r2(key: str, dest_path: str) -> None:
    """Download a file from R2 to local path."""
    client = _r2_client()
    client.download_file(settings.r2_bucket, key, dest_path)