from __future__ import annotations

import uuid
from datetime import UTC, datetime

from koel.usage.events import STREAM_KEY, UsageEvent, UsageRecorder, _encode


class FakeStreamRedis:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def xadd(self, name, fields, *, maxlen=None, approximate=True) -> bytes:
        self.calls.append(
            {"name": name, "fields": fields, "maxlen": maxlen, "approximate": approximate}
        )
        return b"1-0"


def _event(**overrides) -> UsageEvent:
    defaults = {
        "api_key_id": uuid.uuid4(),
        "endpoint": "/rates/{base}",
        "method": "GET",
        "status_code": 200,
        "response_time_ms": 45,
        "bytes_sent": 1200,
        "ip_address": "10.0.0.1",
        "occurred_at": datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return UsageEvent(**defaults)


class TestEncode:
    def test_round_trip_strings(self):
        e = _event()
        d = _encode(e)
        assert d["api_key_id"] == str(e.api_key_id)
        assert d["endpoint"] == "/rates/{base}"
        assert d["method"] == "GET"
        assert d["status_code"] == "200"
        assert d["response_time_ms"] == "45"
        assert d["bytes_sent"] == "1200"
        assert d["ip_address"] == "10.0.0.1"
        assert d["occurred_at"].startswith("2026-04-20T12:00")

    def test_none_values_become_empty_strings(self):
        d = _encode(_event(response_time_ms=None, bytes_sent=None, ip_address=None))
        assert d["response_time_ms"] == ""
        assert d["bytes_sent"] == ""
        assert d["ip_address"] == ""


class TestRecorder:
    def test_record_calls_xadd_with_maxlen(self):
        r = FakeStreamRedis()
        rec = UsageRecorder(r, maxlen=5000)
        rec.record(_event())
        assert len(r.calls) == 1
        call = r.calls[0]
        assert call["name"] == STREAM_KEY
        assert call["maxlen"] == 5000
        assert call["approximate"] is True
        assert call["fields"]["endpoint"] == "/rates/{base}"

    def test_custom_stream_key(self):
        r = FakeStreamRedis()
        rec = UsageRecorder(r, stream_key="custom:stream", maxlen=10)
        rec.record(_event())
        assert r.calls[0]["name"] == "custom:stream"
