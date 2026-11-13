"""S3 access. The API never carries file bytes: the browser posts straight to S3 with a presigned POST.

Two clients: ``client()`` talks to S3 from inside the cluster/Compose network; ``public_client()`` only signs the
presigned POST, using the endpoint the *browser* can reach (moto on localhost in dev, real S3 in production).
In production both endpoints are empty and credentials come from the EC2 instance role (IMDSv2).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ConnectionError, EndpointConnectionError
from django.conf import settings

log = logging.getLogger(__name__)

_CONFIG = Config(
    signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}, s3={"addressing_style": "path"}
)
CHUNK = 1024 * 1024

# Errors worth retrying: network trouble and S3 throttling / 5xx. Anything else (403, 404) is not transient.
TRANSIENT_CODES = {"SlowDown", "InternalError", "ServiceUnavailable", "RequestTimeout", "503", "500"}


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (EndpointConnectionError, ConnectionError)):
        return True
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code")) in TRANSIENT_CODES
    return isinstance(exc, BotoCoreError) and "timeout" in type(exc).__name__.lower()


@cache
def client() -> Any:
    return boto3.client("s3", region_name=settings.AWS_REGION, endpoint_url=settings.S3_ENDPOINT_URL, config=_CONFIG)


@cache
def public_client() -> Any:
    endpoint = settings.S3_PUBLIC_ENDPOINT_URL or settings.S3_ENDPOINT_URL
    return boto3.client("s3", region_name=settings.AWS_REGION, endpoint_url=endpoint, config=_CONFIG)


def reset_clients() -> None:
    """Tests change endpoints at runtime."""
    client.cache_clear()
    public_client.cache_clear()


def presigned_post(key: str, max_bytes: int, expires_in: int) -> dict[str, Any]:
    """POST policy: the exact key, and a size between 1 byte and ``max_bytes``. S3 rejects anything else."""
    return public_client().generate_presigned_post(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Fields={},
        Conditions=[["content-length-range", 1, max_bytes]],
        ExpiresIn=expires_in,
    )


# The production IAM policy grants only PutObject/GetObject on uploads/* and samples/* (no s3:ListBucket). Without
# ListBucket, S3 answers 403 instead of 404 for a key that does not exist, so 403 is read as "missing" here.
MISSING_CODES = {"404", "NoSuchKey", "NotFound", "403", "AccessDenied", "Forbidden"}


def is_missing(exc: BaseException) -> bool:
    return isinstance(exc, ClientError) and str(exc.response.get("Error", {}).get("Code")) in MISSING_CODES


def head_size(key: str) -> int | None:
    """Object size in bytes, or None if it does not exist (or, without ListBucket, cannot be seen)."""
    try:
        resp = client().head_object(Bucket=settings.S3_BUCKET, Key=key)
    except ClientError as e:
        if is_missing(e):
            if str(e.response.get("Error", {}).get("Code")) in ("403", "AccessDenied", "Forbidden"):
                log.info("HEAD %s returned 403: treated as missing (no ListBucket permission by design)", key)
            return None
        raise
    return int(resp["ContentLength"])


def read_prefix(key: str, n_bytes: int) -> bytes:
    """Ranged GET of the first ``n_bytes`` bytes."""
    resp = client().get_object(Bucket=settings.S3_BUCKET, Key=key, Range=f"bytes=0-{n_bytes - 1}")
    return resp["Body"].read()


@dataclass
class Downloaded:
    path: Path
    sha256: str
    size: int


def download_with_sha256(key: str, dest: BinaryIO, path: Path) -> Downloaded:
    """Stream the object to ``dest`` while hashing it, so a 50 MB file is never held in memory."""
    body = client().get_object(Bucket=settings.S3_BUCKET, Key=key)["Body"]
    h = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: body.read(CHUNK), b""):
        h.update(chunk)
        dest.write(chunk)
        size += len(chunk)
    dest.flush()
    return Downloaded(path=path, sha256=h.hexdigest(), size=size)


def put_file(key: str, path: Path) -> None:
    client().upload_file(str(path), settings.S3_BUCKET, key)


def ensure_bucket() -> None:
    """Dev/CI only (S3_CREATE_BUCKET=true): create the bucket with a CORS rule for the Vite origin.
    In production the bucket comes from deploy/aws/s3-setup.sh and the API has no CreateBucket permission."""
    s3 = client()
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=settings.S3_BUCKET)
        log.info("created bucket %s", settings.S3_BUCKET)
    origins = list(settings.CORS_ALLOWED_ORIGINS) or ["http://localhost:5173"]
    s3.put_bucket_cors(
        Bucket=settings.S3_BUCKET,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedMethods": ["POST"],
                    "AllowedOrigins": origins,
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 600,
                }
            ]
        },
    )
