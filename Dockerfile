# syntax=docker/dockerfile:1.7

# =============================================================================
# Stage 1 — builder: install deps into /app/.venv via uv
# =============================================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies (cached separately from source)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Install the project itself
COPY koel ./koel
COPY alembic ./alembic
COPY alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# =============================================================================
# Stage 2 — runtime: slim image, non-root user, no build tools
# =============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        postgresql-client \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1000 koel && \
    useradd --system --uid 1000 --gid koel --shell /bin/bash --create-home koel

WORKDIR /app

COPY --from=builder --chown=koel:koel /app/.venv /app/.venv
COPY --chown=koel:koel koel ./koel
COPY --chown=koel:koel alembic ./alembic
COPY --chown=koel:koel alembic.ini ./
COPY --chown=koel:koel pyproject.toml ./

USER koel

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "koel.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
