from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from koel.backups.orchestrator import BackupOutcome, build_filename, run_backup
from koel.backups.pgdump import DumpResult
from koel.backups.s3 import UploadResult

NOW = datetime(2026, 4, 21, 4, 0, tzinfo=UTC)


def _assert_tmp_cleaned(tmp_path: Path, dump_path: Path | None = None) -> None:
    # Temp dir pattern: tmp_root/koel-backup-*/koel-{timestamp}.dump
    leftovers = list(tmp_path.glob("koel-backup-*"))
    assert leftovers == []
    if dump_path is not None:
        assert not dump_path.exists()


class _FakeRunner:
    def __init__(self, *, size: int = 1000) -> None:
        self.calls: list[Path] = []
        self.size = size

    def run(self, path: Path) -> DumpResult:
        self.calls.append(path)
        path.write_bytes(b"\x00" * self.size)
        return DumpResult(path=path, size_bytes=self.size, duration_seconds=0.05)


class _FakeUploader:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str]] = []

    async def upload(self, path: Path, *, basename: str) -> UploadResult:
        self.calls.append((path, basename))
        return UploadResult(bucket="bucket", key=f"prefix/{basename}")


class TestBuildFilename:
    def test_timestamp_shape(self):
        assert build_filename(NOW) == "koel-20260421-040000.dump"


class TestRunBackup:
    @pytest.mark.asyncio
    async def test_happy_path(self, tmp_path: Path):
        runner = _FakeRunner(size=512)
        uploader = _FakeUploader()
        outcome = await run_backup(runner, uploader, now=NOW, tmp_root=tmp_path)
        assert isinstance(outcome, BackupOutcome)
        assert outcome.filename == "koel-20260421-040000.dump"
        assert outcome.bucket == "bucket"
        assert outcome.key == "prefix/koel-20260421-040000.dump"
        assert outcome.size_bytes == 512
        assert outcome.occurred_at == NOW
        assert outcome.total_duration_seconds >= 0
        assert len(runner.calls) == 1 and len(uploader.calls) == 1

    @pytest.mark.asyncio
    async def test_cleans_up_tmp_on_success(self, tmp_path: Path):
        runner = _FakeRunner()
        uploader = _FakeUploader()
        outcome = await run_backup(runner, uploader, now=NOW, tmp_root=tmp_path)
        _assert_tmp_cleaned(tmp_path, runner.calls[0])
        assert outcome.filename.endswith(".dump")

    @pytest.mark.asyncio
    async def test_cleans_up_tmp_on_failure(self, tmp_path: Path):
        class _BoomRunner:
            def run(self, path: Path) -> DumpResult:
                del path
                raise RuntimeError("pg_dump exploded")

        with pytest.raises(RuntimeError):
            await run_backup(_BoomRunner(), _FakeUploader(), now=NOW, tmp_root=tmp_path)
        _assert_tmp_cleaned(tmp_path)

    @pytest.mark.asyncio
    async def test_to_dict_is_serializable(self, tmp_path: Path):
        outcome = await run_backup(_FakeRunner(), _FakeUploader(), now=NOW, tmp_root=tmp_path)
        d = outcome.to_dict()
        assert d["filename"] == "koel-20260421-040000.dump"
        assert d["occurred_at"] == NOW.isoformat()
        assert isinstance(d["size_bytes"], int)
