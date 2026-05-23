from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from koel.usage.events import UsageEvent
from koel.usage.middleware import UsageMiddleware


class FakeRecorder:
    def __init__(self) -> None:
        self.events: list[UsageEvent] = []
        self.raise_on_record = False

    def record(self, event: UsageEvent) -> None:
        if self.raise_on_record:
            raise RuntimeError("simulated redis failure")
        self.events.append(event)


def _build_app(recorder: FakeRecorder | None, stash_key: uuid.UUID | None = None) -> FastAPI:
    app = FastAPI()
    app.state.usage_recorder = recorder
    app.add_middleware(UsageMiddleware)

    @app.get("/echo/{name}")
    def echo(request: Request, name: str):
        if stash_key is not None:
            request.state.koel_api_key_id = stash_key
        return {"name": name}

    return app


class TestMiddleware:
    def test_no_recorder_installed_is_noop(self):
        app = _build_app(recorder=None, stash_key=uuid.uuid4())
        with TestClient(app) as c:
            r = c.get("/echo/hi")
            assert r.status_code == 200
        # Nothing to assert on recorder — it was None. Test verifies no crash.

    def test_anonymous_request_is_not_tracked(self):
        rec = FakeRecorder()
        app = _build_app(recorder=rec, stash_key=None)
        with TestClient(app) as c:
            r = c.get("/echo/hi")
            assert r.status_code == 200
        assert rec.events == []

    def test_authed_request_emits_event(self):
        key_id = uuid.uuid4()
        rec = FakeRecorder()
        app = _build_app(recorder=rec, stash_key=key_id)
        with TestClient(app) as c:
            r = c.get("/echo/hi")
            assert r.status_code == 200
        assert len(rec.events) == 1
        e = rec.events[0]
        assert e.api_key_id == key_id
        assert e.endpoint == "/echo/{name}"
        assert e.method == "GET"
        assert e.status_code == 200
        assert e.response_time_ms is not None and e.response_time_ms >= 0

    def test_recorder_failure_does_not_break_request(self):
        rec = FakeRecorder()
        rec.raise_on_record = True
        app = _build_app(recorder=rec, stash_key=uuid.uuid4())
        with TestClient(app) as c:
            # Would blow up without the try/except in the middleware.
            r = c.get("/echo/hi")
            assert r.status_code == 200
