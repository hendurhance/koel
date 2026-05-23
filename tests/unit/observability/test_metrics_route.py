from __future__ import annotations

from fastapi.testclient import TestClient
from koel.api.main import create_app


class TestMetricsRoute:
    def test_metrics_endpoint_responds_with_prometheus_text(self):
        app = create_app()
        client = TestClient(app)
        r = client.get("/metrics")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")
        # The register is process-global; any metric we've touched should show.
        assert "koel_" in r.text
