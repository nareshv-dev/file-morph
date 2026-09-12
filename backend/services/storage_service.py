from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Protocol

from backend.config import settings


class StorageService(Protocol):
    def put(self, user_id: str, data: bytes, suffix: str) -> str: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str | None) -> None: ...


class LocalStorageService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid storage key.")
        return path

    def put(self, user_id: str, data: bytes, suffix: str) -> str:
        safe_suffix = suffix.lower() if suffix.startswith(".") and suffix[1:].isalnum() else ".bin"
        key = f"{user_id}/{secrets.token_urlsafe(24)}{safe_suffix}"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return key

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str | None) -> None:
        if not key:
            return
        path = self._path(key)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass

    def cleanup_expired_objects(self, retention_hours: int) -> None:
        cutoff = time.time() - retention_hours * 3600
        for path in self.root.rglob("*"):
            if path.is_file() and path.stat().st_mtime <= cutoff:
                self.delete(path.relative_to(self.root).as_posix())

    def ready(self) -> bool:
        return self.root.is_dir()


class S3StorageService:
    def __init__(self) -> None:
        import boto3
        self.bucket = os.environ["S3_BUCKET"]
        self.client = boto3.client("s3", endpoint_url=os.getenv("S3_ENDPOINT_URL") or None)

    def put(self, user_id: str, data: bytes, suffix: str) -> str:
        key = f"{user_id}/{secrets.token_urlsafe(24)}{suffix}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def get(self, key: str) -> bytes:
        try:
            result = self.client.get_object(Bucket=self.bucket, Key=key)
            return result["Body"].read()
        except self.client.exceptions.NoSuchKey as exc:
            raise FileNotFoundError(key) from exc

    def delete(self, key: str | None) -> None:
        if key: self.client.delete_object(Bucket=self.bucket, Key=key)

    def ready(self) -> bool:
        self.client.head_bucket(Bucket=self.bucket)
        return True


storage: StorageService = S3StorageService() if settings.storage_provider == "s3" else LocalStorageService(settings.storage_path)
