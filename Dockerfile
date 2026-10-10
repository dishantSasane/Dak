FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/app

FROM base AS deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" "sqlalchemy[asyncio]>=2.0" asyncpg alembic \
    pydantic pydantic-settings redis arq langgraph langgraph-checkpoint-postgres \
    google-genai pgvector pdfplumber html2text

FROM base AS final
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY app ./app
COPY scripts ./scripts
COPY alembic.ini ./
COPY alembic ./alembic
RUN useradd -m appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
