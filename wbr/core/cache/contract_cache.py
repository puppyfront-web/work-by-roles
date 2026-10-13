"""契约绑定语义缓存（精确缓存）（SPEC-004 §2）。

Key = sha256(f"{contract_hash}|{question_hash}|{evidence_snapshot_id}")
失效双保险：契约变更主动 invalidate + 命中时被动校验条目 contract_hash。
"""
from __future__ import annotations

import threading
import time
import unicodedata

from pydantic import BaseModel, Field

from wbr.core.canonical import canonical_json, sha256_hex
from wbr.core.cache.backends import CacheBackend, InMemoryCacheBackend
from wbr.core.contract.models import RoleContract


# ---- Key 三要素 ----
def normalize_question(question: str) -> str:
    """问题规范化：去首尾空白 + 全角半角归一（NDKFK→NFKC）。"""
    return unicodedata.normalize("NFKC", question.strip())


def question_hash(question: str) -> str:
    return sha256_hex(canonical_json(normalize_question(question)))


def evidence_snapshot_id(evidence: list[str] | None) -> str:
    if not evidence:
        return "none"
    return sha256_hex(canonical_json(list(evidence)))


def cache_key(contract: RoleContract, question: str, evidence: list[str] | None) -> str:
    raw = f"{contract.content_hash}|{question_hash(question)}|{evidence_snapshot_id(evidence)}"
    return sha256_hex(raw)


class CacheStats(BaseModel):
    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 6) if total else 0.0


class CacheEntry(BaseModel):
    contract_hash: str
    question_hash: str
    evidence_snapshot_id: str
    value: dict
    created_at: float = Field(default_factory=time.time)


class ContractBoundCache:
    """契约绑定缓存：契约变更自动失效；enabled=False 全直通（规则6）。"""

    def __init__(
        self,
        backend: CacheBackend | None = None,
        *,
        enabled: bool = True,
        max_entries: int = 4096,
    ) -> None:
        self.enabled = enabled
        self._backend = backend if backend is not None else InMemoryCacheBackend(max_entries=max_entries)
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

    # ---- 统计 ----
    @property
    def stats(self) -> CacheStats:
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            invalidations=self._invalidations,
            evictions=getattr(self._backend, "evictions", 0),
        )

    def reset_stats(self) -> None:
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

    # ---- API ----
    def get(self, contract: RoleContract, question: str, evidence: list[str] | None = None) -> dict | None:
        if not self.enabled:
            with self._lock:
                self._misses += 1
            return None
        key = cache_key(contract, question, evidence)
        raw = self._backend.get(key)
        if raw is None:
            with self._lock:
                self._misses += 1
            return None
        entry = CacheEntry.model_validate(raw)
        # 被动校验：条目契约哈希与当前契约不一致 → 丢弃并计失效（不脏数据）
        if entry.contract_hash != contract.content_hash:
            self._backend.delete(key)
            with self._lock:
                self._invalidations += 1
                self._misses += 1
            return None
        with self._lock:
            self._hits += 1
        return entry.value

    def put(
        self, contract: RoleContract, question: str, evidence: list[str] | None, value: dict
    ) -> None:
        if not self.enabled:
            return
        entry = CacheEntry(
            contract_hash=contract.content_hash,
            question_hash=question_hash(question),
            evidence_snapshot_id=evidence_snapshot_id(evidence),
            value=value,
        )
        self._backend.set(cache_key(contract, question, evidence), entry.model_dump())

    def invalidate_contract(self, contract: RoleContract | str) -> int:
        """主动失效：按契约哈希清除全部条目。"""
        target = contract if isinstance(contract, str) else contract.content_hash
        removed = 0
        if hasattr(self._backend, "delete_by_prefix"):
            removed = self._backend.delete_by_prefix(f"{target}|")
        # 缓存键是最终 sha256，前缀不可匹配时退化为全扫比对
        for key in self._backend.keys():
            raw = self._backend.get(key)
            if raw and raw.get("contract_hash") == target:
                self._backend.delete(key)
                removed += 1
        with self._lock:
            self._invalidations += removed
        return removed

    def clear(self) -> None:
        self._backend.clear()
        self.reset_stats()
