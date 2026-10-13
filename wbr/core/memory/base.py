"""四层隔离记忆：记录模型与存储协议（SPEC-002 §5）。"""
from __future__ import annotations

import threading
import time
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from wbr.core.constants import MemoryLayer


class MemoryRecord(BaseModel):
    key: str
    value: Any
    layer: MemoryLayer
    role_id: str | None = None
    session_id: str | None = None
    ts: float = Field(default_factory=time.time)


@runtime_checkable
class MemoryStore(Protocol):
    """记忆存储协议：namespace = (layer, scope) 二维隔离。"""

    def get(self, namespace: tuple[str, str], key: str) -> MemoryRecord | None: ...

    def set(self, namespace: tuple[str, str], key: str, record: MemoryRecord) -> None: ...

    def delete(self, namespace: tuple[str, str], key: str) -> None: ...

    def keys(self, namespace: tuple[str, str]) -> list[str]: ...

    def append(self, namespace: tuple[str, str], key: str, value: Any) -> None: ...

    def clear(self, namespace: tuple[str, str]) -> None: ...


class InMemoryMemoryStore:
    """线程安全的进程内存储实现（测试与单机默认）。"""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], dict[str, MemoryRecord]] = {}
        self._lock = threading.RLock()

    def get(self, namespace: tuple[str, str], key: str) -> MemoryRecord | None:
        with self._lock:
            return self._data.get(namespace, {}).get(key)

    def set(self, namespace: tuple[str, str], key: str, record: MemoryRecord) -> None:
        with self._lock:
            self._data.setdefault(namespace, {})[key] = record

    def delete(self, namespace: tuple[str, str], key: str) -> None:
        with self._lock:
            self._data.get(namespace, {}).pop(key, None)

    def keys(self, namespace: tuple[str, str]) -> list[str]:
        with self._lock:
            return sorted(self._data.get(namespace, {}).keys())

    def append(self, namespace: tuple[str, str], key: str, value: Any) -> None:
        with self._lock:
            ns = self._data.setdefault(namespace, {})
            record = ns.get(key)
            if record is None:
                ns[key] = MemoryRecord(
                    key=key, value=[value], layer=MemoryLayer(namespace[0])
                )
            else:
                if isinstance(record.value, list):
                    record.value = [*record.value, value]
                else:
                    record.value = [record.value, value]

    def clear(self, namespace: tuple[str, str]) -> None:
        with self._lock:
            self._data.pop(namespace, None)
