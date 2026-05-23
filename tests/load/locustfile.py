from __future__ import annotations

import os
import random

from locust import HttpUser, between, task

# ISO 4217 codes seeded in koel/data/*.csv. Not exhaustive — enough variety
# that the hot set isn't always the same three pairs.
BASES = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY")
TARGETS = ("USD", "EUR", "GBP", "JPY", "NGN", "INR", "BRL", "ZAR", "SGD", "HKD")


def _pick_pair() -> tuple[str, str]:
    base = random.choice(BASES)
    target = random.choice(TARGETS)
    while target == base:
        target = random.choice(TARGETS)
    return base, target


class KoelUser(HttpUser):
    # Between-request think time roughly matches a human-ish client. For
    # server-side throughput tests, override with ``--wait-time 0``.
    wait_time = between(0.01, 0.05)

    def on_start(self) -> None:
        key = os.environ.get("KOEL_API_KEY", "")
        if key:
            # Koel authenticates the data plane via the X-API-Key header.
            self.client.headers.update({"X-API-Key": key})

    @task(20)
    def rate_current(self) -> None:
        base, target = _pick_pair()
        self.client.get(
            f"/rates/current?base={base}&target={target}",
            name="/rates/current",
        )

    @task(3)
    def rate_convert(self) -> None:
        base, target = _pick_pair()
        self.client.get(
            f"/rates/convert?from={base}&to={target}&amount=100",
            name="/rates/convert",
        )

    @task(2)
    def rate_history(self) -> None:
        base, target = _pick_pair()
        # Small window so the query hits a single partition; the plan's 500
        # rps target is for hot-path ``/rates/current``, not history scans.
        self.client.get(
            f"/rates/history?base={base}&target={target}",
            name="/rates/history",
        )

    @task(1)
    def healthz(self) -> None:
        self.client.get("/healthz")
