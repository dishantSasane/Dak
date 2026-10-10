"""Redis client and ARQ queue helpers."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)
    return _redis


def reset_redis() -> None:
    """Test hook: drop the cached client."""
    global _redis
    _redis = None


async def enqueue_email_processing(email_id: int) -> None:
    """Push a process_email job. Called only after the email row is committed
    (02-architecture.md §1.1: insert before enqueue)."""
    pool = await create_pool(RedisSettings.from_dsn(get_settings().REDIS_URL))
    try:
        await pool.enqueue_job("process_email", email_id)
    finally:
        await pool.aclose()


async def cache_get_json(key: str) -> Any | None:
    raw = await get_redis().get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    await get_redis().set(key, json.dumps(value, default=str), ex=ttl_seconds)
