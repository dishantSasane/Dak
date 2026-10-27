import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Synthetic local settings; never contact an LLM or email provider in tests.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/inbox_triage_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("GEMINI_API_KEY", "test-only")
os.environ.setdefault("CLOUDMAILIN_SECRET", "test-only")


import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def isolated_redis_client():
    from app.redis_client import get_redis, reset_redis

    reset_redis()
    yield
    await get_redis().aclose()
    reset_redis()


@pytest.fixture
async def database():
    url = os.environ["DATABASE_URL"]
    assert url.rsplit("/", 1)[-1].endswith("_test"), "Use an isolated *_test database"
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE cases CASCADE"))
    async with factory() as session:
        yield session, factory
    await engine.dispose()
