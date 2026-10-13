"""Redis 存储后端：键编码 wbr:{layer}:{scope}:{key}，客户端注入（D-04）。"""
from __future__ import annotations

import fnmatch
import json
from typing import Any

from wbr.adapters.storage.base import Namespace


class RedisStorageBackend:
    """接受任意遵循 redis-py 子集协议的客户端（真实 redis / 测试 Fake）。"""

    def __init__(self, client: Any, *, prefix: str = "wbr", default_ttl: int | None = None) -> None:
        self._client = client
        self._prefix = prefix
        self._default_ttl = default_ttl

    def _key(self, namespace: Namespace, key: str) -> str:
        return f"{self._prefix}:{namespace[0]}:{namespace[1]}:{key}"

    _ENC = "utf-8"

    def get(self, namespace: Namespace, key: str) -> Any | None:
        raw = self._client.get(self._key(namespace, key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode(self._ENC)
        return json.loads(raw)

    def set(self, namespace: Namespace, key: str, value: Any, *, ttl: int | None = None) -> None:
        k = self._key(namespace, key)
        payload = json.dumps(value, ensure_ascii=False)
        effective = ttl if ttl is not None else self._default_ttl
        if effective is not None:
            self._client.setex(k, effective, payload)
        else:
            self._client.set(k, payload)

    def delete(self, namespace: Namespace, key: str) -> None:
        self._client.delete(self._key(namespace, key))

    def keys(self, namespace: Namespace) -> list[str]:
        pattern = f"{self._prefix}:{namespace[0]}:{namespace[1]}:*"
        out = []
        for k in self._client.keys(pattern):
            if isinstance(k, bytes):
                k = k.decode(self._ENC)
            out.append(k.rsplit(":", 1)[-1])
        return sorted(out)

    def append(self, namespace: Namespace, key: str, value: Any) -> None:
        self._client.rpush(self._key(namespace, key), json.dumps(value, ensure_ascii=False))

    def clear(self, namespace: Namespace) -> None:
        pattern = f"{self._prefix}:{namespace[0]}:{namespace[1]}:*"
        for k in list(self._client.keys(pattern)):
            self._client.delete(k)


def list_matches(client_keys, pattern: str) -> list:  # pragma: no cover - Fake 辅助
    return [k for k in client_keys if fnmatch.fnmatch(k, pattern)]
