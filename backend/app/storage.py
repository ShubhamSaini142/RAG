"""Object storage (MinIO / S3) access for raw uploaded files."""
import boto3
from botocore.client import Config

from app.config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.s3_bucket)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    get_s3_client().put_object(
        Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type
    )


def download_bytes(key: str) -> bytes:
    obj = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
    return obj["Body"].read()


def delete_object(key: str) -> None:
    get_s3_client().delete_object(Bucket=settings.s3_bucket, Key=key)
