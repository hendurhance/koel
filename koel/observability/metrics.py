from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# Latency buckets tuned for the service's stated P99 target (<20ms hot path)
# but with enough tail to catch slow /history scans and misbehaving proxies.
HTTP_LATENCY_BUCKETS = (
    0.001,
    0.0025,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

http_requests_total = Counter(
    "koel_http_requests_total",
    "Total HTTP requests received by the API, labelled by route and outcome.",
    labelnames=("method", "route", "status"),
)

http_request_duration_seconds = Histogram(
    "koel_http_request_duration_seconds",
    "End-to-end HTTP request duration measured at the middleware seam.",
    labelnames=("method", "route"),
    buckets=HTTP_LATENCY_BUCKETS,
)


scrape_pairs_total = Counter(
    "koel_scrape_pairs_total",
    "Pair scrape attempts, labelled by outcome.",
    labelnames=("outcome",),  # consensus | no_consensus | no_sources | unknown_pair
)

scrape_source_fetches_total = Counter(
    "koel_scrape_source_fetches_total",
    "Individual source fetches within a pair scrape.",
    labelnames=("source", "outcome"),  # outcome: ok | error | timeout
)

circuit_transitions_total = Counter(
    "koel_circuit_transitions_total",
    "Circuit breaker state transitions per source.",
    labelnames=("source", "from_status", "to_status"),
)


usage_events_flushed_total = Counter(
    "koel_usage_events_flushed_total",
    "Usage events persisted from the Redis stream to Postgres.",
)

usage_flush_duration_seconds = Histogram(
    "koel_usage_flush_duration_seconds",
    "Duration of a single usage-stream flush run.",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


backup_runs_total = Counter(
    "koel_backup_runs_total",
    "Backup task runs, labelled by outcome.",
    labelnames=("outcome",),  # ok | failed | skipped
)

backup_duration_seconds = Histogram(
    "koel_backup_duration_seconds",
    "End-to-end backup duration (dump + upload).",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

backup_last_size_bytes = Gauge(
    "koel_backup_last_size_bytes",
    "Size of the most recent successful backup in bytes.",
)


def render_metrics() -> tuple[bytes, str]:
    """Serialize the default registry into Prometheus text format."""
    return generate_latest(), CONTENT_TYPE_LATEST


__all__ = [
    "backup_duration_seconds",
    "backup_last_size_bytes",
    "backup_runs_total",
    "circuit_transitions_total",
    "http_request_duration_seconds",
    "http_requests_total",
    "render_metrics",
    "scrape_pairs_total",
    "scrape_source_fetches_total",
    "usage_events_flushed_total",
    "usage_flush_duration_seconds",
]
