"""存储后端协议（SPEC-003 §2 / D-04）。

Redis / 内存实现均落在此协议上；客户端可注入，便于测试与替换。
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

Namespace = tuple[str, str]


@runtime_checkable
class StorageBackend(Protocol):
    """键值存储抽象：namespace 二维隔离（如 layer/scope）。"""

    def get(self, namespace: Namespace, key: str) -> Any | None: ...

    def set(self, namespace: Namespace, key: str, value: Any, *, ttl: int | None = None) -> None: ...

    def delete(self, namespace: Namespace, key: str) -> None: ...

    def keys(self, namespace: Namespace) -> list[str]: ...

    def append(self, namespace: Namespace, key: str, value: Any) -> None: ...

    def clear(self, namespace: Namespace) -> None: ...
