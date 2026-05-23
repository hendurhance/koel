from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from koel.backups.pgdump import PgDumpError, PgDumpRunner, normalize_database_url


class TestNormalizeDatabaseUrl:
    def test_strips_sqlalchemy_driver_suffix(self):
        assert (
            normalize_database_url("postgresql+psycopg://u:p@h:5432/db")
            == "postgresql://u:p@h:5432/db"
        )

    def test_passthrough_when_already_bare(self):
        assert normalize_database_url("postgresql://u@h/db") == "postgresql://u@h/db"


class _StubRunner:
    def __init__(self, *, returncode: int = 0, stderr: str = "", write_bytes: int = 1024) -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.write_bytes = write_bytes
        self.calls: list[list[str]] = []

    def __call__(self, cmd, timeout):
        del timeout
        self.calls.append(list(cmd))
        output_path = _extract_file_arg(cmd)
        if self.write_bytes and self.returncode == 0:
            Path(output_path).write_bytes(b"\x00" * self.write_bytes)
        return subprocess.CompletedProcess(
            args=list(cmd), returncode=self.returncode, stdout="", stderr=self.stderr
        )


def _extract_file_arg(cmd) -> str:
    for arg in cmd:
        if arg.startswith("--file="):
            return arg[len("--file=") :]
    raise AssertionError("no --file= arg in command")


class TestPgDumpRunner:
    def test_build_command_includes_custom_format_and_dsn(self, tmp_path: Path):
        runner = PgDumpRunner("postgresql+psycopg://u:p@h/db", runner=_StubRunner(write_bytes=0))
        out = tmp_path / "dump.bin"
        cmd = runner.build_command(out)
        assert cmd[0] == "pg_dump"
        assert "--format=custom" in cmd
        assert "--no-owner" in cmd
        assert "--no-privileges" in cmd
        assert f"--file={out}" in cmd
        # DSN is the last arg and carries the libpq form.
        assert cmd[-1] == "postgresql://u:p@h/db"

    def test_run_returns_size_and_duration(self, tmp_path: Path):
        stub = _StubRunner(write_bytes=2048)
        runner = PgDumpRunner("postgresql://h/db", runner=stub)
        result = runner.run(tmp_path / "dump.bin")
        assert result.size_bytes == 2048
        assert result.duration_seconds >= 0
        assert len(stub.calls) == 1

    def test_run_raises_on_nonzero_return(self, tmp_path: Path):
        stub = _StubRunner(returncode=1, stderr="connection refused")
        runner = PgDumpRunner("postgresql://h/db", runner=stub)
        with pytest.raises(PgDumpError) as exc:
            runner.run(tmp_path / "dump.bin")
        assert exc.value.returncode == 1
        assert "connection refused" in str(exc.value)
