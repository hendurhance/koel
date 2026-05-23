from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from koel.api.deps import get_db, require_rates_read
from koel.api.main import create_app
from koel.db import queries
from koel.db.queries import CurrencyRow, CurrentRateRow, HistoryRow, SourceRow

NOW = datetime(2026, 4, 19, 12, 0, tzinfo=UTC)


@pytest.fixture
def app_with_stub(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, dict[str, Any]]:
    """Build the FastAPI app and swap the DB functions for test stubs.

    Returns the client plus a mutable `canned` dict so each test can dial
    in what the stubs return without defining a new fixture.
    """
    canned: dict[str, Any] = {
        "pair": None,
        "base_rows": [],
        "history": [],
        "currencies": [],
        "sources": [],
        "known_codes": set(),
    }

    def _get_db():
        # Dependency returns something truthy — routes only forward it to
        # patched functions, which ignore it.
        yield object()

    monkeypatch.setattr(queries, "get_current_pair", lambda _s, b, t: canned["pair"])
    monkeypatch.setattr(queries, "get_current_for_base", lambda _s, b, **_k: canned["base_rows"])
    monkeypatch.setattr(queries, "get_history", lambda *a, **kw: canned["history"])
    monkeypatch.setattr(queries, "list_active_currencies", lambda _s: canned["currencies"])
    monkeypatch.setattr(queries, "list_sources_with_health", lambda _s: canned["sources"])
    monkeypatch.setattr(queries, "known_currency_codes", lambda _s, codes: canned["known_codes"])

    # The route modules import these names at import time. Patch there too.
    from koel.api.routes import currencies as cur_route
    from koel.api.routes import rates as rates_route
    from koel.api.routes import sources as sources_route

    monkeypatch.setattr(rates_route, "get_current_pair", lambda _s, b, t: canned["pair"])
    monkeypatch.setattr(
        rates_route, "get_current_for_base", lambda _s, b, **_k: canned["base_rows"]
    )
    monkeypatch.setattr(rates_route, "get_history", lambda *a, **kw: canned["history"])
    monkeypatch.setattr(
        rates_route, "known_currency_codes", lambda _s, codes: canned["known_codes"]
    )
    monkeypatch.setattr(cur_route, "list_active_currencies", lambda _s: canned["currencies"])
    monkeypatch.setattr(sources_route, "list_sources_with_health", lambda _s: canned["sources"])

    app = create_app()
    app.dependency_overrides[get_db] = _get_db
    # Bypass key auth for these data-plane tests — they focus on read logic,
    # not the auth layer (that's test_auth_routes.py + test_keys_routes.py).
    app.dependency_overrides[require_rates_read] = lambda: None
    return TestClient(app), canned


class TestCurrentSinglePair:
    def test_returns_pair_when_present(self, app_with_stub):
        client, canned = app_with_stub
        canned["pair"] = CurrentRateRow(
            base="USD",
            target="EUR",
            rate=Decimal("0.8500"),
            confidence=Decimal("1.000"),
            sources_count=3,
            observed_at=NOW,
        )
        r = client.get("/rates/current", params={"base": "usd", "target": "eur"})
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "base": "USD",
            "target": "EUR",
            "rate": "0.8500",
            "confidence": "1.000",
            "sources_count": 3,
            "observed_at": "2026-04-19T12:00:00Z",
        }

    def test_404_when_missing(self, app_with_stub):
        client, canned = app_with_stub
        canned["pair"] = None
        r = client.get("/rates/current", params={"base": "USD", "target": "EUR"})
        assert r.status_code == 404


class TestCurrentBulk:
    def test_returns_all_targets(self, app_with_stub):
        client, canned = app_with_stub
        canned["base_rows"] = [
            CurrentRateRow("USD", "EUR", Decimal("0.85"), Decimal("1.000"), 3, NOW),
            CurrentRateRow("USD", "GBP", Decimal("0.74"), Decimal("1.000"), 3, NOW),
        ]
        r = client.get("/rates/current", params={"base": "USD"})
        assert r.status_code == 200
        body = r.json()
        assert body["base"] == "USD"
        assert len(body["rates"]) == 2
        assert body["rates"][0]["target"] == "EUR"
        assert body["rates"][0]["rate"] == "0.85"

    def test_404_when_empty(self, app_with_stub):
        client, canned = app_with_stub
        canned["base_rows"] = []
        r = client.get("/rates/current", params={"base": "USD"})
        assert r.status_code == 404


class TestHistory:
    def test_returns_points(self, app_with_stub):
        client, canned = app_with_stub
        canned["history"] = [
            HistoryRow(Decimal("0.8500"), Decimal("1.000"), 3, NOW),
            HistoryRow(Decimal("0.8490"), Decimal("0.900"), 2, NOW - timedelta(hours=1)),
        ]
        r = client.get("/rates/history", params={"base": "USD", "target": "EUR"})
        assert r.status_code == 200
        body = r.json()
        assert body["base"] == "USD"
        assert body["target"] == "EUR"
        assert len(body["points"]) == 2
        assert body["points"][0]["rate"] == "0.8500"

    def test_limit_validation(self, app_with_stub):
        client, _ = app_with_stub
        r = client.get("/rates/history", params={"base": "USD", "target": "EUR", "limit": 99999})
        assert r.status_code == 422

    def test_empty_history_returns_200_empty_points(self, app_with_stub):
        client, canned = app_with_stub
        canned["history"] = []
        r = client.get("/rates/history", params={"base": "USD", "target": "EUR"})
        assert r.status_code == 200
        assert r.json()["points"] == []


class TestConvert:
    def test_computes_result(self, app_with_stub):
        client, canned = app_with_stub
        canned["pair"] = CurrentRateRow("USD", "EUR", Decimal("0.8500"), Decimal("1.000"), 3, NOW)
        r = client.get("/rates/convert", params={"from": "USD", "to": "EUR", "amount": "100"})
        assert r.status_code == 200
        body = r.json()
        assert body["from"] == "USD"
        assert body["to"] == "EUR"
        assert body["rate"] == "0.8500"
        assert body["result"] == "85.0000"

    def test_404_unknown_currency_lists_missing(self, app_with_stub):
        client, canned = app_with_stub
        canned["pair"] = None
        canned["known_codes"] = {"USD"}  # EUR is "missing" in the stub
        r = client.get("/rates/convert", params={"from": "USD", "to": "XXX", "amount": "1"})
        assert r.status_code == 404
        assert "XXX" in r.json()["detail"]

    def test_amount_must_be_positive(self, app_with_stub):
        client, _ = app_with_stub
        r = client.get("/rates/convert", params={"from": "USD", "to": "EUR", "amount": "0"})
        assert r.status_code == 422


class TestCurrencies:
    def test_lists_currencies(self, app_with_stub):
        client, canned = app_with_stub
        canned["currencies"] = [
            CurrencyRow("USD", "US Dollar", "$", 2, "major"),
            CurrencyRow("JPY", "Japanese Yen", "¥", 0, "major"),
        ]
        r = client.get("/currencies")
        assert r.status_code == 200
        codes = [c["code"] for c in r.json()["currencies"]]
        assert codes == ["USD", "JPY"]


class TestSources:
    def test_lists_sources_with_health(self, app_with_stub):
        client, canned = app_with_stub
        canned["sources"] = [
            SourceRow(
                slug="xe",
                name="XE",
                weight=Decimal("1.200"),
                is_active=True,
                circuit_state="closed",
                consecutive_failures=0,
                total_requests=100,
                total_failures=3,
                avg_latency_ms=Decimal("120.50"),
                last_success_at=NOW,
                last_failure_at=None,
            ),
        ]
        r = client.get("/sources")
        assert r.status_code == 200
        s = r.json()["sources"][0]
        assert s["slug"] == "xe"
        assert s["health"]["circuit_state"] == "closed"
        assert s["health"]["avg_latency_ms"] == "120.50"

    def test_source_without_health_returns_null(self, app_with_stub):
        client, canned = app_with_stub
        canned["sources"] = [
            SourceRow(
                slug="ghost",
                name="Ghost",
                weight=Decimal("1.000"),
                is_active=False,
                circuit_state=None,
                consecutive_failures=None,
                total_requests=None,
                total_failures=None,
                avg_latency_ms=None,
                last_success_at=None,
                last_failure_at=None,
            ),
        ]
        r = client.get("/sources")
        assert r.status_code == 200
        assert r.json()["sources"][0]["health"] is None
