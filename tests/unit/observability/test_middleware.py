from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient
from koel.observability.metrics import http_requests_total, render_metrics
from koel.observability.middleware import REQUEST_ID_HEADER, RequestMetricsMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestMetricsMiddleware)

    @app.get("/echo/{name}")
    def echo(name: str):
        return {"name": name}

    return app


class TestRequestId:
    def test_generates_request_id_when_missing(self):
        app = _build_app()
        with TestClient(app) as c:
            r = c.get("/echo/hi")
        assert r.status_code == 200
        assert REQUEST_ID_HEADER in r.headers
        assert re.fullmatch(r"[0-9a-f]{32}", r.headers[REQUEST_ID_HEADER])

    def test_echoes_inbound_request_id(self):
        app = _build_app()
        inbound = "fixed-request-id-123"
        with TestClient(app) as c:
            r = c.get("/echo/hi", headers={REQUEST_ID_HEADER: inbound})
        assert r.headers[REQUEST_ID_HEADER] == inbound


class TestMetrics:
    def test_records_matched_route_template(self):
        app = _build_app()
        before = _count_for(method="GET", route="/echo/{name}", status="200")
        with TestClient(app) as c:
            c.get("/echo/a")
            c.get("/echo/b")
        after = _count_for(method="GET", route="/echo/{name}", status="200")
        # Two new requests; both matched the template, not the raw path.
        assert after - before >= 2

    def test_unmatched_route_is_bucketed(self):
        app = _build_app()
        before = _count_for(method="GET", route="<unmatched>", status="404")
        with TestClient(app) as c:
            c.get("/this-does-not-exist")
        after = _count_for(method="GET", route="<unmatched>", status="404")
        assert after - before == 1


def _count_for(*, method: str, route: str, status: str) -> float:
    sample = http_requests_total.labels(method=method, route=route, status=status)
    # prometheus_client stores counters in ``_value.get()``; accessing it is
    # the cleanest way to peek without re-parsing the exposition format.
    return sample._value.get()


class TestMetricsEndpointUsable:
    def test_render_after_traffic_contains_route(self):
        app = _build_app()
        with TestClient(app) as c:
            c.get("/echo/x")
        body, _ = render_metrics()
        assert b'route="/echo/{name}"' in body
