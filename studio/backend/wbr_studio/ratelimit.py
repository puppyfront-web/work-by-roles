"""认证接口的滑动窗口。默认进程内；多副本把 STUDIO_RATE_LIMIT_BACKEND 设为 redis。"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict, deque

from wbr_studio.settings import get_settings

_log = logging.getLogger("wbr_studio.ratelimit")
_REDIS_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
  redis.call('EXPIRE', key, window)
  return 0
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window)
return 1
"""


class MemoryLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        settings = get_settings()
        limit = settings.studio_auth_rate_limit
        window = settings.studio_auth_rate_window_seconds
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class RedisLimiter:
    def __init__(self, client) -> None:
        self._client = client

    def allow(self, key: str) -> bool:
        settings = get_settings()
        now = time.time()
        member = f"{now}:{uuid.uuid4().hex}"
        allowed = self._client.eval(
            _REDIS_LUA,
            1,
            f"wbr-studio:rl:{key}",
            now,
            settings.studio_auth_rate_window_seconds,
            settings.studio_auth_rate_limit,
            member,
        )
        return bool(allowed)


_memory = MemoryLimiter()
_redis: RedisLimiter | None = None


def get_limiter():
    if get_settings().studio_rate_limit_backend == "redis":
        global _redis
        if _redis is None:
            import redis

            _redis = RedisLimiter(redis.Redis.from_url(get_settings().redis_url))
        return _redis
    return _memory


def reset_limiter() -> None:
    global _redis
    _memory.reset()
    _redis = None


def client_ip(request) -> str:
    if request.client is None or not request.client.host:
        return "-"
    return request.client.host


def allow_auth(request, email: str | None = None) -> bool:
    limiter = get_limiter()
    try:
        ip_ok = limiter.allow(f"auth:{client_ip(request)}")
        email_ok = True if not email else limiter.allow(f"auth-email:{email}")
    except Exception as exc:
        _log.warning("rate limit backend failed open (%s)", type(exc).__name__)
        return True
    return ip_ok and email_ok
