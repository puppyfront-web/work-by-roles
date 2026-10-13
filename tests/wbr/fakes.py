"""测试假件：FakeRedis（redis-py 最小子集协议）。"""
from __future__ import annotations

import fnmatch
import threading


class FakeRedis:
    """实现 RedisStorageBackend 用到的命令子集：get/set/setex/delete/keys/rpush。"""

    def __init__(self) -> None:
        self._strings: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}
        self._ttls: dict[str, int] = {}
        self._lock = threading.RLock()

    # ---- strings ----
    def set(self, key: str, value: str) -> bool:
        with self._lock:
            self._strings[key] = value
            self._ttls.pop(key, None)
        return True

    def setex(self, key: str, ttl: int, value: str) -> bool:
        with self._lock:
            self._strings[key] = value
            self._ttls[key] = ttl
        return True

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._strings.get(key)

    def delete(self, *keys: str) -> int:
        n = 0
        with self._lock:
            for k in keys:
                if k in self._strings:
                    self._strings.pop(k)
                    n += 1
                if k in self._lists:
                    self._lists.pop(k)
                    n += 1
                self._ttls.pop(k, None)
        return n

    def keys(self, pattern: str) -> list[str]:
        with self._lock:
            all_keys = list(self._strings) + list(self._lists)
        return [k for k in all_keys if fnmatch.fnmatch(k, pattern)]

    # ---- lists ----
    def rpush(self, key: str, *values: str) -> int:
        with self._lock:
            self._lists.setdefault(key, []).extend(values)
            return len(self._lists[key])

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        with self._lock:
            lst = self._lists.get(key, [])
        if end == -1:
            return lst[start:]
        return lst[start : end + 1]

    # ---- 观测 ----
    def ttl_of(self, key: str) -> int | None:
        return self._ttls.get(key)
