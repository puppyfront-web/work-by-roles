"""StorageBackend → Core MemoryStore 协议桥接，提供持久化记忆门面。"""
from __future__ import annotations

from typing import Any

from wbr.adapters.storage.base import StorageBackend
from wbr.core.constants import MemoryLayer
from wbr.core.memory.base import MemoryRecord
from wbr.core.memory.hub import MemoryHub


class StorageBackedMemoryStore:
    """把 Core 的 MemoryStore 协议落到任意 StorageBackend（JSON 序列化）。"""

    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend

    def get(self, namespace: tuple[str, str], key: str) -> MemoryRecord | None:
        raw = self._backend.get(namespace, key)
        return MemoryRecord.model_validate(raw) if raw is not None else None

    def set(self, namespace: tuple[str, str], key: str, record: MemoryRecord) -> None:
        self._backend.set(namespace, key, record.model_dump())

    def delete(self, namespace: tuple[str, str], key: str) -> None:
        self._backend.delete(namespace, key)

    def keys(self, namespace: tuple[str, str]) -> list[str]:
        return self._backend.keys(namespace)

    def append(self, namespace: tuple[str, str], key: str, value: Any) -> None:
        existing = self.get(namespace, key)
        if existing is None:
            self.set(
                namespace,
                key,
                MemoryRecord(
                    key=key, value=[value], layer=MemoryLayer(namespace[0])
                ),
            )
        else:
            values = existing.value if isinstance(existing.value, list) else [existing.value]
            existing.value = [*values, value]
            self.set(namespace, key, existing)

    def clear(self, namespace: tuple[str, str]) -> None:
        self._backend.clear(namespace)


def persistent_memory_hub(backend: StorageBackend, **hub_kw) -> MemoryHub:
    """构建以 StorageBackend 为底的持久化记忆门面（角色记忆完全隔离）。"""
    return MemoryHub(StorageBackedMemoryStore(backend), **hub_kw)
