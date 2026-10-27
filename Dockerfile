FROM node:22-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.13.1 AS uv
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/srv/app/.venv \
    PATH="/srv/app/.venv/bin:$PATH"
WORKDIR /srv/app

COPY --from=uv /uv /uvx /bin/
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY scripts ./scripts
COPY data/seeds ./data/seeds
COPY data/corpus ./data/corpus
COPY --from=frontend-build /src/frontend/dist ./frontend/dist
COPY alembic.ini ./
COPY alembic ./alembic
RUN uv sync --frozen --no-dev \
    && useradd --create-home appuser

USER appuser
EXPOSE 10000
CMD ["python", "scripts/render_start.py", "web"]
