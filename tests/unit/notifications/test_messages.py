from __future__ import annotations

from datetime import UTC, datetime

from koel.notifications.messages import (
    BackupFailure,
    BackupSuccess,
    CircuitTransition,
    CrawlCycleSummary,
    format_backup_failure,
    format_backup_success,
    format_circuit_closed,
    format_circuit_opened,
    format_crawl_complete,
)

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


class TestCrawlComplete:
    def test_shape(self):
        s = CrawlCycleSummary(
            enqueued=12,
            scraped=11,
            had_consensus=9,
            circuit_transitions=1,
            duration_seconds=4.37,
            occurred_at=NOW,
        )
        msg = format_crawl_complete(s)
        assert "Crawl cycle complete" in msg.text
        assert "11/12" in msg.text
        assert "4.4s" in msg.text
        assert msg.blocks  # rich blocks included
        payload = msg.to_payload()
        assert payload["text"] == msg.text
        assert "blocks" in payload


class TestCircuitOpened:
    def test_contains_slug_and_failure_count(self):
        t = CircuitTransition(
            source_slug="trading-economics",
            from_status="closed",
            to_status="open",
            consecutive_failures=5,
            opened_at=NOW,
        )
        msg = format_circuit_opened(t)
        assert "trading-economics" in msg.text
        assert "5 consecutive failures" in msg.text
        payload = msg.to_payload()
        assert payload["text"].startswith(":rotating_light:")


class TestCircuitClosed:
    def test_recovery_message(self):
        t = CircuitTransition(
            source_slug="xrates",
            from_status="half_open",
            to_status="closed",
            consecutive_failures=0,
            opened_at=None,
        )
        msg = format_circuit_closed(t)
        assert "recovered" in msg.text
        assert "xrates" in msg.text


class TestBackupSuccess:
    def test_contains_filename_and_size(self):
        b = BackupSuccess(
            filename="koel-20260421-040000.dump",
            bucket="my-bucket",
            key="koel/koel-20260421-040000.dump",
            size_bytes=2 * 1024 * 1024,
            duration_seconds=3.2,
            occurred_at=NOW,
        )
        msg = format_backup_success(b)
        assert "koel-20260421-040000.dump" in msg.text
        assert "2.0 MB" in msg.text
        assert "3.2s" in msg.text
        payload = msg.to_payload()
        assert "blocks" in payload


class TestBackupFailure:
    def test_flags_failure_and_truncates_long_errors(self):
        long_err = "x" * 600
        f = BackupFailure(error=long_err, occurred_at=NOW)
        msg = format_backup_failure(f)
        assert msg.text.startswith(":rotating_light:")
        assert "failed" in msg.text
        # Long error must be trimmed so Slack doesn't reject the payload.
        assert len(msg.text) < 600
