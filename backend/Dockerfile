# syntax=docker/dockerfile:1
# Production image for the FastAPI backend (Render / any container host).
FROM python:3.12-slim

# uv from its official image: fast, reproducible installs straight from uv.lock.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first (cached until the lockfile changes); no dev tools in prod.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

EXPOSE 8000
# Render injects $PORT; default to 8000 for a plain `docker run`.
CMD ["sh", "-c", "uv run --frozen uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
