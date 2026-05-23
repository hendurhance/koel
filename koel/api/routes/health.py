from typing import Any

import redis
from fastapi import APIRouter, Response, status
from sqlalchemy import create_engine, text

from koel import __version__
from koel.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness probe")
def healthz() -> dict[str, str]:
    """Process is alive. Never touches external systems."""
    return {"status": "ok", "version": __version__}


@router.get("/readyz", summary="Readiness probe")
def readyz(response: Response) -> dict[str, Any]:
    """Ready to serve traffic: DB + Redis reachable."""
    settings = get_settings()
    checks: dict[str, str] = {}
    all_ok = True

    try:
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
        all_ok = False

    try:
        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {type(exc).__name__}"
        all_ok = False

    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ok" if all_ok else "degraded", "checks": checks}
