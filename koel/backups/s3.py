from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import aioboto3

if TYPE_CHECKING:
    from collections.abc import Awaitable


@dataclass(frozen=True, slots=True)
class UploadResult:
    bucket: str
    key: str


class _SessionFactory(Protocol):
    """Signature shared by ``aioboto3.Session`` and test doubles."""

    def __call__(
        self,
        *,
        aws_access_key_id: str | None,
        aws_secret_access_key: str | None,
        region_name: str | None,
    ) -> Any: ...


class S3Uploader:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str = "",
        secret_access_key: str = "",
        prefix: str = "",
        session_factory: _SessionFactory | None = None,
    ) -> None:
        self._bucket = bucket
        self._region = region
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._prefix = prefix.strip("/")
        self._session_factory: _SessionFactory = session_factory or aioboto3.Session

    @property
    def bucket(self) -> str:
        return self._bucket

    def build_key(self, basename: str) -> str:
        return f"{self._prefix}/{basename}" if self._prefix else basename

    async def upload(self, path: Path, *, basename: str) -> UploadResult:
        key = self.build_key(basename)
        session = self._session_factory(
            aws_access_key_id=self._access_key_id or None,
            aws_secret_access_key=self._secret_access_key or None,
            region_name=self._region or None,
        )
        client_cm = session.client("s3")
        async with client_cm as s3:
            awaitable: Awaitable[Any] = s3.upload_file(str(path), self._bucket, key)
            await awaitable

        return UploadResult(bucket=self._bucket, key=key)


__all__ = ["S3Uploader", "UploadResult"]
