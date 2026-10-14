"""高级缓存语义匹配（V1.x F3 / SPEC-007 §3）。

语义命中前置：契约哈希 + 证据快照精确一致，仅问题文本允许近似（防脏读）。
embedding 注入，Core 不内置模型；索引为内存实现。
"""
from __future__ import annotations

import math
import threading
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from wbr.core.cache.contract_cache import ContractBoundCache
from wbr.core.contract.models import RoleContract


@runtime_checkable
class EmbeddingFn(Protocol):
    def embed(self, text: str) -> list[float]: ...


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class SemanticStats(BaseModel):
    """兼容 CacheStats 字段 + 语义命中扩展。"""

    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    evictions: int = 0
    semantic_hits: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 6) if total else 0.0


class _SemanticEntry(BaseModel):
    contract_hash: str
    evidence_id: str
    question: str
    vector: list[float]
    value: dict


class SemanticCache:
    """两级缓存：精确层（ContractBoundCache）+ 语义近似层（同契约内）。"""

    def __init__(
        self,
        exact: ContractBoundCache,
        *,
        embedder: EmbeddingFn,
        threshold: float = 0.92,
        enabled: bool = True,
    ) -> None:
        self.exact = exact
        self.embedder = embedder
        self.threshold = threshold
        self.enabled = enabled
        self._index: dict[str, list[_SemanticEntry]] = {}   # contract_hash -> entries
        self._lock = threading.RLock()
        self._semantic_hits = 0

    # ---- 统计 ----
    @property
    def stats(self) -> SemanticStats:
        base = self.exact.stats
        return SemanticStats(
            hits=base.hits, misses=base.misses,
            invalidations=base.invalidations, evictions=base.evictions,
            semantic_hits=self._semantic_hits,
        )

    def reset_stats(self) -> None:
        self.exact.reset_stats()
        self._semantic_hits = 0

    # ---- API ----
    def get(self, contract: RoleContract, question: str, evidence=None, *,
            semantic: bool = True) -> tuple[dict | None, str]:
        """返回 (value, hit_kind)；hit_kind ∈ exact | semantic | miss。"""
        value = self.exact.get(contract, question, evidence)
        if value is not None:
            return value, "exact"
        if self.enabled and semantic:
            hit = self._semantic_lookup(contract, question, evidence)
            if hit is not None:
                self._bump_semantic()
                return hit, "semantic"
        return None, "miss"

    def put(self, contract: RoleContract, question: str, evidence, value: dict) -> None:
        self.exact.put(contract, question, evidence, value)
        if not self.enabled:
            return
        from wbr.core.cache.contract_cache import evidence_snapshot_id

        entry = _SemanticEntry(
            contract_hash=contract.content_hash,
            evidence_id=evidence_snapshot_id(evidence),
            question=question,
            vector=self.embedder.embed(question),
            value=value,
        )
        with self._lock:
            self._index.setdefault(contract.content_hash, []).append(entry)

    def invalidate_contract(self, contract: RoleContract | str) -> int:
        target = contract if isinstance(contract, str) else contract.content_hash
        with self._lock:
            self._index.pop(target, None)
        return self.exact.invalidate_contract(contract)

    def clear(self) -> None:
        with self._lock:
            self._index.clear()
        self.exact.clear()
        self._semantic_hits = 0

    # ---- 内部 ----
    def _semantic_lookup(self, contract: RoleContract, question: str, evidence) -> dict | None:
        from wbr.core.cache.contract_cache import evidence_snapshot_id

        eid = evidence_snapshot_id(evidence)
        vector = self.embedder.embed(question)
        best: tuple[float, _SemanticEntry] | None = None
        with self._lock:
            for entry in self._index.get(contract.content_hash, []):
                if entry.evidence_id != eid:
                    continue  # 证据快照必须精确一致
                sim = cosine(vector, entry.vector)
                if sim >= self.threshold and (best is None or sim > best[0]):
                    best = (sim, entry)
        return best[1].value if best else None

    def _bump_semantic(self) -> None:
        self._semantic_hits += 1
