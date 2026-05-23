from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from koel.backups.s3 import S3Uploader


class _FakeClientCM:
    def __init__(self, client):
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb


class _FakeClient:
    def __init__(self):
        self.upload_calls: list[tuple[str, str, str]] = []

    async def upload_file(self, path: str, bucket: str, key: str):
        self.upload_calls.append((path, bucket, key))


class _FakeSession:
    def __init__(self, client: _FakeClient):
        self._client = client
        self.kwargs: dict[str, Any] | None = None

    def client(self, name: str):
        del name
        return _FakeClientCM(self._client)


class TestBuildKey:
    def test_combines_prefix_and_basename(self):
        u = S3Uploader(bucket="b", region="us-east-1", prefix="koel/backups")
        assert u.build_key("dump.bin") == "koel/backups/dump.bin"

    def test_no_prefix_returns_basename(self):
        u = S3Uploader(bucket="b", region="us-east-1", prefix="")
        assert u.build_key("dump.bin") == "dump.bin"

    def test_strips_surrounding_slashes(self):
        u = S3Uploader(bucket="b", region="us-east-1", prefix="/koel/backups/")
        assert u.build_key("dump.bin") == "koel/backups/dump.bin"


class TestUpload:
    @pytest.mark.asyncio
    async def test_upload_calls_client_with_expected_args(self, tmp_path: Path):
        fake = _FakeClient()
        captured: dict[str, Any] = {}

        def factory(**kwargs):
            captured.update(kwargs)
            return _FakeSession(fake)

        p = tmp_path / "dump.bin"
        p.write_bytes(b"hello")
        u = S3Uploader(
            bucket="backups",
            region="us-west-2",
            access_key_id="AK",
            secret_access_key="SK",
            prefix="koel",
            session_factory=factory,
        )
        result = await u.upload(p, basename="dump.bin")

        assert fake.upload_calls == [(str(p), "backups", "koel/dump.bin")]
        assert result.bucket == "backups"
        assert result.key == "koel/dump.bin"
        assert captured["region_name"] == "us-west-2"
        assert captured["aws_access_key_id"] == "AK"
        assert captured["aws_secret_access_key"] == "SK"
