"""
MinIO storage helper for Compass.

Wraps the official `minio` Python client. Used by the scraping pipeline
(landing zone) and by the transformation script (processed zone).

The two-bucket pattern: raw scraped HTML lands in `compass-landing`; the
transformer reads from there, cleans the HTML, and writes the result to
`compass-processed` with the file renamed to `<identifier>.<ext>`.
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Optional

from minio import Minio
from minio.error import S3Error


logger = logging.getLogger(__name__)


class MinioStorage:
    """Thin wrapper around the minio client with helpers for our use case."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
    ) -> None:
        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._endpoint = endpoint

    def ensure_bucket(self, bucket: str) -> None:
        """Create the bucket if it doesn't exist (idempotent)."""
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)
            logger.info("Created MinIO bucket: %s", bucket)

    def put_bytes(
        self,
        bucket: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to bucket/object_name. Returns the object_name."""
        self._client.put_object(
            bucket_name=bucket,
            object_name=object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return object_name

    def get_bytes(self, bucket: str, object_name: str) -> bytes:
        """Read an object's bytes."""
        response = self._client.get_object(bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def list_objects(self, bucket: str, prefix: str = "") -> list[str]:
        """Return all object names in the bucket (optionally prefix-filtered)."""
        return [obj.object_name for obj in self._client.list_objects(bucket, prefix=prefix, recursive=True)]

    def object_exists(self, bucket: str, object_name: str) -> bool:
        try:
            self._client.stat_object(bucket, object_name)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise


def sha256_hex(data: bytes) -> str:
    """Return the SHA256 hex digest of `data`."""
    return hashlib.sha256(data).hexdigest()
