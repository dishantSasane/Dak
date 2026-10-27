"""Cross-worker pacing using Redis server time and separate eval scheduling."""

import asyncio

from app.config import get_settings
from app.redis_client import get_redis

_RESERVE = """
local t = redis.call('TIME')
local now = tonumber(t[1])*1000 + tonumber(t[2])/1000
local interval = tonumber(ARGV[1])
local ready = math.max(now, tonumber(redis.call('GET', KEYS[1]) or '0'))
if ARGV[2] == 'eval' then
  ready = math.max(ready, tonumber(redis.call('GET', KEYS[2]) or '0'))
  redis.call('SET', KEYS[2], ready + interval*2, 'PX', 180000)
end
redis.call('SET', KEYS[1], ready + interval, 'PX', 180000)
return math.ceil(ready-now)
"""


class RateLimiter:
    async def acquire(self, *, eval_run: bool = False) -> None:
        rpm = max(1, get_settings().RPM_LIMIT)
        wait_ms = await get_redis().execute_command(
            "EVAL",
            _RESERVE,
            2,
            "gemini:next-call",
            "gemini:eval-next",
            str(60_000 / rpm),
            "eval" if eval_run else "live",
        )
        await asyncio.sleep(max(0, int(wait_ms)) / 1000)
