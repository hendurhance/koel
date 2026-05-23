from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from koel.observability.logging import get_logger
from koel.usage.events import UsageEvent, UsageRecorder

log = get_logger("koel.usage.middleware")


def _route_path(request: Request) -> str:
    """Template path (``/rates/{base}``) when routing matched, else raw path."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path or request.url.path


def _bytes_sent(response: Response) -> int | None:
    raw = response.headers.get("content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


class UsageMiddleware(BaseHTTPMiddleware):
    """Stashes latency + dispatches a usage event for each authenticated call.

    The authenticated-key id is stashed on ``request.state.koel_api_key_id``
    by ``get_current_api_key``; if it's absent, the request is anonymous and
    we skip tracking.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        recorder: UsageRecorder | None = getattr(request.app.state, "usage_recorder", None)
        if recorder is None:
            return response

        key_id = getattr(request.state, "koel_api_key_id", None)
        if not isinstance(key_id, uuid.UUID):
            return response

        event = UsageEvent(
            api_key_id=key_id,
            endpoint=_route_path(request)[:128],
            method=request.method[:8],
            status_code=response.status_code,
            response_time_ms=elapsed_ms,
            bytes_sent=_bytes_sent(response),
            ip_address=request.client.host if request.client else None,
            occurred_at=datetime.now(tz=UTC),
        )
        try:
            recorder.record(event)
        except Exception as exc:
            # Best-effort — a failed record must never fail the user's request.
            log.warning("usage.record.failed", error=str(exc))

        return response
