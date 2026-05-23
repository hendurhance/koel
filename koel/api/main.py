from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis import Redis

from koel import __version__
from koel.api.routes import (
    admin,
    auth,
    currencies,
    health,
    keys,
    metrics,
    rates,
    sources,
    usage,
)
from koel.config import get_settings
from koel.observability.logging import configure_logging, get_logger
from koel.observability.middleware import RequestMetricsMiddleware
from koel.usage.events import UsageRecorder
from koel.usage.middleware import UsageMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = get_logger("koel.api")
    log.info("api.startup", version=__version__)
    settings = get_settings()
    # Recorder stays None if Redis can't be reached — middleware will no-op.
    # We ping so we fail fast here rather than on every request's try/except.
    if settings.USAGE_TRACKING_ENABLED:
        try:
            redis = Redis.from_url(settings.REDIS_URL, decode_responses=False)
            redis.ping()
            app.state.usage_recorder = UsageRecorder(redis)
            log.info("usage.recorder.ready")
        except Exception as exc:
            # Observability must not block startup; stay disabled if Redis isn't up.
            log.warning("usage.recorder.unavailable", error=str(exc))
            app.state.usage_recorder = None
    yield
    log.info("api.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Koel",
        version=__version__,
        description="Self-hostable exchange rate API.",
        lifespan=lifespan,
    )
    # Default — lifespan (or tests) set the real recorder. Middleware no-ops
    # when this is None, so unit tests that don't trigger lifespan are safe.
    app.state.usage_recorder = None
    # Middleware order matters: outermost runs first on request, last on
    # response. We want metrics wrapping usage so latency reflects the full
    # handler including usage recording.
    app.add_middleware(UsageMiddleware)
    app.add_middleware(RequestMetricsMiddleware)
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(rates.router)
    app.include_router(currencies.router)
    app.include_router(sources.router)
    app.include_router(auth.router)
    app.include_router(keys.router)
    app.include_router(usage.router)
    app.include_router(admin.router)
    return app


app = create_app()
