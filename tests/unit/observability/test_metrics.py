from __future__ import annotations

from koel.observability.metrics import (
    backup_runs_total,
    circuit_transitions_total,
    http_requests_total,
    render_metrics,
    scrape_pairs_total,
)


class TestRenderMetrics:
    def test_returns_text_payload_and_content_type(self):
        body, content_type = render_metrics()
        assert content_type.startswith("text/plain")
        assert b"koel_" in body

    def test_exposition_includes_known_metric_names(self):
        # Touch each counter so it shows up in the exposition output even on
        # a cold registry.
        http_requests_total.labels(method="GET", route="/healthz", status="200").inc(0)
        scrape_pairs_total.labels(outcome="consensus").inc(0)
        circuit_transitions_total.labels(source="s", from_status="closed", to_status="open").inc(0)
        backup_runs_total.labels(outcome="ok").inc(0)

        body, _ = render_metrics()
        text = body.decode("utf-8")
        assert "koel_http_requests_total" in text
        assert "koel_scrape_pairs_total" in text
        assert "koel_circuit_transitions_total" in text
        assert "koel_backup_runs_total" in text
