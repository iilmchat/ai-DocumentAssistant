"""T9: абстракция хранилища файлов — local volume или S3/MinIO.

Файлы по-прежнему сохраняются и локально (для обратной совместимости и OCR-воркера);
при STORAGE_BACKEND=s3 дополнительно загружаются в object storage, а local-файл можно удалить.
"""

import os
from typing import BinaryIO

from app.core.config import settings
from app.core.logging import log


class StorageBackend:
    def save(self, key: str, data: bytes) -> str:
        raise NotImplementedError

    def open(self, key: str) -> BinaryIO:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def presigned_url(self, key: str) -> str | None:
        return None


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or settings.UPLOAD_DIR
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.base_dir, os.path.basename(key))

    def save(self, key: str, data: bytes) -> str:
        path = self._path(key)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def open(self, key: str) -> BinaryIO:
        return open(self._path(key), "rb")

    def delete(self, key: str) -> None:
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)


class S3Storage(StorageBackend):
    def __init__(self):
        import boto3  # type: ignore[import-not-found]

        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        self.bucket = settings.S3_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def save(self, key: str, data: bytes) -> str:
        from io import BytesIO

        self.client.upload_fileobj(BytesIO(data), self.bucket, key)
        return f"s3://{self.bucket}/{key}"

    def open(self, key: str) -> BinaryIO:
        import io

        body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        return io.BytesIO(body)

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def presigned_url(self, key: str) -> str | None:
        return str(
            self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=settings.S3_PRESIGN_TTL,
            )
        )


_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _backend
    if _backend is None:
        if settings.STORAGE_BACKEND == "s3":
            _backend = S3Storage()
            log.info("storage.backend", backend="s3")
        else:
            _backend = LocalStorage()
            log.info("storage.backend", backend="local")
    return _backend


def reset_storage() -> None:
    global _backend
    _backend = None
