from __future__ import annotations

import time
from typing import Any, cast

from curl_cffi.requests import AsyncSession, BrowserTypeLiteral, Response
from curl_cffi.requests.exceptions import HTTPError, RequestException, Timeout
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from koel.observability.logging import get_logger
from koel.scraping.exceptions import BlockedError, NetworkError, RateLimitError

log = get_logger("koel.scraping.client")

DEFAULT_IMPERSONATE = "chrome124"
DEFAULT_TIMEOUT_SECONDS = 10.0


class ScrapeClient:
    """Thin wrapper over curl_cffi.AsyncSession.

    Responsibilities: retry with jittered backoff, map HTTP errors to our
    exception taxonomy, track latency. Does NOT parse responses — that's
    the scraper's job.
    """

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        default_impersonate: str = DEFAULT_IMPERSONATE,
        max_attempts: int = 3,
    ) -> None:
        self._timeout = timeout
        self._default_impersonate = default_impersonate
        self._max_attempts = max_attempts
        self._session: AsyncSession[Response] | None = None

    async def __aenter__(self) -> ScrapeClient:
        self._session = AsyncSession()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def get_text(self, url: str, *, impersonate: str | None = None) -> tuple[str, int]:
        response = await self._get(url, impersonate=impersonate)
        return response["text"], response["latency_ms"]

    async def get_json(self, url: str, *, impersonate: str | None = None) -> tuple[Any, int]:
        response = await self._get(url, impersonate=impersonate)
        try:
            return response["json"](), response["latency_ms"]
        except ValueError as exc:
            raise NetworkError(f"invalid JSON from {url}") from exc

    async def _get(self, url: str, *, impersonate: str | None) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("ScrapeClient must be used as an async context manager")

        imp = impersonate or self._default_impersonate
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential_jitter(initial=0.5, max=8.0),
            retry=retry_if_exception_type((NetworkError,)),
            reraise=True,
        ):
            with attempt:
                return await self._attempt(url, imp)
        raise NetworkError(f"unreachable after {self._max_attempts} attempts: {url}")

    async def _attempt(self, url: str, impersonate: str) -> dict[str, Any]:
        assert self._session is not None
        started = time.perf_counter()
        try:
            resp = await self._session.get(
                url,
                impersonate=cast(BrowserTypeLiteral, impersonate),
                timeout=self._timeout,
                allow_redirects=True,
            )
        except Timeout as exc:
            raise NetworkError(f"timeout fetching {url}") from exc
        except (HTTPError, RequestException) as exc:
            raise NetworkError(f"transport error fetching {url}: {exc}") from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        status = resp.status_code

        if status == 429:
            raise RateLimitError(f"rate limited by {url}")
        if status == 403:
            raise BlockedError(f"blocked by {url}")
        if status >= 500:
            raise NetworkError(f"{status} from {url}")
        if status >= 400:
            raise NetworkError(f"{status} from {url}")

        log.debug("scrape.http.ok", url=url, status=status, latency_ms=latency_ms)
        return {"text": resp.text, "json": resp.json, "latency_ms": latency_ms}
