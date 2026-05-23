from __future__ import annotations

import uuid
from datetime import UTC, datetime

from koel.usage.events import UsageEvent, _encode
from koel.usage.flush import flush_stream


class FakeStream:
    """Minimal xrange/xdel stand-in with bytes-valued fields like real Redis."""

    def __init__(self) -> None:
        self.entries: list[tuple[bytes, dict[bytes, bytes]]] = []
        self.deleted: list[bytes] = []

    def add(self, entry_id: str, fields: dict[str, str]) -> None:
        self.entries.append(
            (entry_id.encode(), {k.encode(): v.encode() for k, v in fields.items()})
        )

    def xrange(self, name, min="-", max="+", count=None):
        del name, min, max
        return self.entries[: count or len(self.entries)]

    def xdel(self, name, *ids):
        del name
        self.deleted.extend(ids)
        # Simulate removal from the stream.
        keep = [(eid, data) for eid, data in self.entries if eid not in ids]
        removed = len(self.entries) - len(keep)
        self.entries = keep
        return removed


class FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple] = []
        self.flushes = 0

    def execute(self, stmt, params=None):
        self.executed.append((stmt, params))

    def flush(self):
        self.flushes += 1


def _event() -> UsageEvent:
    return UsageEvent(
        api_key_id=uuid.uuid4(),
        endpoint="/rates/{base}",
        method="GET",
        status_code=200,
        response_time_ms=45,
        bytes_sent=1200,
        ip_address="10.0.0.1",
        occurred_at=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
    )


class TestFlush:
    def test_empty_stream_is_noop(self):
        stream = FakeStream()
        session = FakeSession()
        result = flush_stream(session, stream)
        assert result.flushed == 0
        assert result.from_id is None
        assert stream.deleted == []
        assert session.executed == []

    def test_drains_and_deletes(self):
        stream = FakeStream()
        e1, e2 = _event(), _event()
        stream.add("1-0", _encode(e1))
        stream.add("2-0", _encode(e2))

        session = FakeSession()
        result = flush_stream(session, stream)

        assert result.flushed == 2
        assert result.from_id == "1-0"
        assert result.to_id == "2-0"
        # One bulk insert with both rows in params.
        assert len(session.executed) == 1
        _, params = session.executed[0]
        assert len(params) == 2
        assert params[0]["endpoint"] == "/rates/{base}"
        assert params[0]["status_code"] == 200
        # All ids were XDEL'd.
        assert stream.deleted == [b"1-0", b"2-0"]

    def test_respects_batch_size(self):
        stream = FakeStream()
        for i in range(5):
            stream.add(f"{i}-0", _encode(_event()))
        session = FakeSession()
        result = flush_stream(session, stream, batch_size=2)
        assert result.flushed == 2
        # Remaining 3 entries still in stream after the deletion.
        assert len(stream.entries) == 3

    def test_malformed_entry_is_dropped_but_id_deleted(self):
        stream = FakeStream()
        # Missing required fields → decode raises KeyError → skip row, keep id.
        stream.add("1-0", {"endpoint": "/x"})
        stream.add("2-0", _encode(_event()))
        session = FakeSession()
        result = flush_stream(session, stream)
        # Only the well-formed row got inserted.
        assert result.flushed == 1
        _, params = session.executed[0]
        assert len(params) == 1
        # But both ids are XDEL'd so we don't retry the broken one forever.
        assert stream.deleted == [b"1-0", b"2-0"]

    def test_all_malformed_skips_insert(self):
        stream = FakeStream()
        stream.add("1-0", {"endpoint": "/x"})
        session = FakeSession()
        result = flush_stream(session, stream)
        assert result.flushed == 0
        assert session.executed == []
        assert stream.deleted == [b"1-0"]
