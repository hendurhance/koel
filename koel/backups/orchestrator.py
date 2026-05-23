from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from koel.backups.pgdump import PgDumpRunner
from koel.backups.s3 import S3Uploader

DUMP_FILENAME_FMT = "koel-%Y%m%d-%H%M%S.dump"


@dataclass(frozen=True, slots=True)
class BackupOutcome:
    filename: str
    bucket: str
    key: str
    size_bytes: int
    dump_duration_seconds: float
    total_duration_seconds: float
    occurred_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "filename": self.filename,
            "bucket": self.bucket,
            "key": self.key,
            "size_bytes": self.size_bytes,
            "dump_duration_seconds": self.dump_duration_seconds,
            "total_duration_seconds": self.total_duration_seconds,
            "occurred_at": self.occurred_at.isoformat(),
        }


def build_filename(now: datetime) -> str:
    return now.strftime(DUMP_FILENAME_FMT)


async def run_backup(
    runner: PgDumpRunner,
    uploader: S3Uploader,
    *,
    now: datetime,
    tmp_root: Path | None = None,
) -> BackupOutcome:
    filename = build_filename(now)
    # Dump to a private temp dir and clean it up unconditionally; we never
    # retain backups on the local disk.
    with tempfile.TemporaryDirectory(prefix="koel-backup-", dir=tmp_root) as tmp:
        dump_path = Path(tmp) / filename
        import time  # local import — perf_counter is the only thing we need

        t0 = time.perf_counter()
        dump_result = runner.run(dump_path)
        upload_result = await uploader.upload(dump_path, basename=filename)
        total = time.perf_counter() - t0

    return BackupOutcome(
        filename=filename,
        bucket=upload_result.bucket,
        key=upload_result.key,
        size_bytes=dump_result.size_bytes,
        dump_duration_seconds=dump_result.duration_seconds,
        total_duration_seconds=total,
        occurred_at=now,
    )


__all__ = ["BackupOutcome", "build_filename", "run_backup"]
