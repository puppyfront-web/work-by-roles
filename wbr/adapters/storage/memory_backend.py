"""进程内存储后端（测试与单机默认）。"""
from __future__ import annotations

import threading
from typing import Any

from wbr.adapters.storage.base import Namespace


class InMemoryStorageBackend:
    def __init__(self) -> None:
        self._data: dict[Namespace, dict[str, list[Any]]] = {}
        self._lock = threading.RLock()

    def get(self, namespace: Namespace, key: str) -> Any | None:
        with self._lock:
            bucket = self._data.get(namespace, {}).get(key)
            return bucket[-1] if bucket else None

    def set(self, namespace: Namespace, key: str, value: Any, *, ttl: int | None = None) -> None:
        with self._lock:
            self._data.setdefault(namespace, {})[key] = [value]  # ttl 在内存实现中不模拟过期

    def delete(self, namespace: Namespace, key: str) -> None:
        with self._lock:
            self._data.get(namespace, {}).pop(key, None)

    def keys(self, namespace: Namespace) -> list[str]:
        with self._lock:
            return sorted(self._data.get(namespace, {}).keys())

    def append(self, namespace: Namespace, key: str, value: Any) -> None:
        with self._lock:
            self._data.setdefault(namespace, {}).setdefault(key, []).append(value)

    def clear(self, namespace: Namespace) -> None:
        with self._lock:
            self._data.pop(namespace, None)
