from __future__ import annotations

import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PG_DUMP_BIN = "pg_dump"
DEFAULT_TIMEOUT_SECONDS = 600.0


SubprocessRunner = Callable[[Sequence[str], float], "subprocess.CompletedProcess[str]"]


def _default_runner(cmd: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — args are a fixed list, not user input
        list(cmd),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@dataclass(frozen=True, slots=True)
class DumpResult:
    path: Path
    size_bytes: int
    duration_seconds: float


class PgDumpError(RuntimeError):
    """Raised when ``pg_dump`` returns a non-zero exit code."""

    def __init__(self, returncode: int, stderr: str) -> None:
        super().__init__(f"pg_dump exited with {returncode}: {stderr.strip()[:500]}")
        self.returncode = returncode
        self.stderr = stderr


def normalize_database_url(url: str) -> str:
    """SQLAlchemy-style DSN → libpq-style.

    ``postgresql+psycopg://...`` is what the app uses; ``pg_dump`` only
    understands the bare ``postgresql://`` form.
    """
    if url.startswith("postgresql+"):
        _, _, rest = url.partition("://")
        return f"postgresql://{rest}"
    return url


class PgDumpRunner:
    def __init__(
        self,
        database_url: str,
        *,
        pg_dump_bin: str = DEFAULT_PG_DUMP_BIN,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        runner: SubprocessRunner | None = None,
    ) -> None:
        self._dsn = normalize_database_url(database_url)
        self._bin = pg_dump_bin
        self._timeout = timeout
        self._runner = runner or _default_runner

    def build_command(self, output_path: Path) -> list[str]:
        return [
            self._bin,
            "--format=custom",
            "--compress=6",
            "--no-owner",
            "--no-privileges",
            f"--file={output_path}",
            self._dsn,
        ]

    def run(self, output_path: Path) -> DumpResult:
        started = time.perf_counter()
        result = self._runner(self.build_command(output_path), self._timeout)
        duration = time.perf_counter() - started

        if result.returncode != 0:
            raise PgDumpError(result.returncode, result.stderr or "")

        size = output_path.stat().st_size if output_path.exists() else 0
        return DumpResult(path=output_path, size_bytes=size, duration_seconds=duration)


__all__ = [
    "DumpResult",
    "PgDumpError",
    "PgDumpRunner",
    "SubprocessRunner",
    "normalize_database_url",
]
