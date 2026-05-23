from __future__ import annotations

import contextvars
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from koel.observability.metrics import (
    http_request_duration_seconds,
    http_requests_total,
)

REQUEST_ID_HEADER = "X-Request-ID"
# contextvar so structlog can pick it up anywhere within the request scope.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Records request count + latency and binds a request ID for logging.

    Route template (``/rates/{base}/{target}``) is the metric label — NOT the
    raw path. Using raw paths would blow up cardinality the first time a
    scanner hit us with random URLs.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)

        method = request.method
        start = time.perf_counter()
        status = "500"
        try:
            response: Response = await call_next(request)
            status = str(response.status_code)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            elapsed = time.perf_counter() - start
            route = _route_template(request)
            http_requests_total.labels(method=method, route=route, status=status).inc()
            http_request_duration_seconds.labels(method=method, route=route).observe(elapsed)
            structlog.contextvars.unbind_contextvars("request_id")
            request_id_var.reset(token)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return str(path)
    # No match (404 / 405) — bucket under a single label to keep cardinality
    # bounded. The method + status labels still carry the useful signal.
    return "<unmatched>"


__all__ = ["REQUEST_ID_HEADER", "RequestMetricsMiddleware", "request_id_var"]
