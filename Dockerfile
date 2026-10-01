# syntax=docker/dockerfile:1
# NEMLab Python backend — one build context, two independently runnable
# application images: `--target api` (FastAPI/uvicorn) and `--target worker`
# (non-HTTP poller). Both run as a non-root user from locked uv dependencies;
# the pinned interpreter matches `.python-version` and SciPy/HiGHS ships in the
# venv as binary wheels.

FROM ghcr.io/astral-sh/uv:0.11.29 AS uvbin

FROM python:3.13.14-slim AS deps
COPY --from=uvbin /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock .python-version ./
COPY core/pyproject.toml core/
COPY core/src core/src/
COPY infrastructure/pyproject.toml infrastructure/
COPY infrastructure/src infrastructure/src/
COPY api/pyproject.toml api/
COPY api/src api/src/
COPY worker/pyproject.toml worker/
COPY worker/src worker/src/

FROM deps AS deps-api
RUN uv sync --locked --no-dev --no-editable --package nemlab-api

FROM deps AS deps-worker
RUN uv sync --locked --no-dev --no-editable --package nemlab-worker

FROM deps AS deps-migrate
RUN uv sync --locked --no-dev --no-editable --package nemlab-infrastructure

FROM python:3.13.14-slim AS runtime
RUN groupadd --system nemlab \
    && useradd --system --gid nemlab --home-dir /app nemlab
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER nemlab
WORKDIR /app

FROM runtime AS api
COPY --from=deps-api --chown=nemlab:nemlab /app/.venv /app/.venv
EXPOSE 8080
CMD ["nemlab-api"]

FROM runtime AS worker
COPY --from=deps-worker --chown=nemlab:nemlab /app/.venv /app/.venv
CMD ["nemlab-worker"]

# Schema management: `docker run --rm <image>-migrate migrate|check|adopt`.
FROM runtime AS migrate
COPY --from=deps-migrate --chown=nemlab:nemlab /app/.venv /app/.venv
COPY --chown=nemlab:nemlab alembic.ini migrations ./
ENTRYPOINT ["python", "-m", "nemlab_infrastructure.migrate"]
CMD ["check"]
