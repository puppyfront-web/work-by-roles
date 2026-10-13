"""缓存后端协议与进程内 LRU 实现（SPEC-004 §2）。"""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    def get(self, key: str) -> dict | None: ...

    def set(self, key: str, value: dict) -> None: ...

    def delete(self, key: str) -> None: ...

    def keys(self) -> list[str]: ...

    def clear(self) -> None: ...


class InMemoryCacheBackend:
    """线程安全 LRU 后端（进程内默认）。"""

    def __init__(self, max_entries: int = 4096) -> None:
        self.max_entries = max_entries
        self._data: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.RLock()
        self.evictions = 0

    def get(self, key: str) -> dict | None:
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)  # LRU 触碰
            return value

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)
                self.evictions += 1

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def delete_by_prefix(self, prefix: str) -> int:
        """删除所有以 prefix 开头的键（契约失效用）。"""
        removed = 0
        with self._lock:
            for key in [k for k in self._data if k.startswith(prefix)]:
                self._data.pop(key)
                removed += 1
        return removed
