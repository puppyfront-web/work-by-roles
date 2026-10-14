"""TC-V1.1-SEM：高级语义缓存匹配。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import expert_contract
from wbr.core.cache import ContractBoundCache
from wbr.core.cache.semantic import SemanticCache, cosine


class FakeEmbedder:
    """确定性词袋向量：问题语义 = 关键词集合。"""

    def embed(self, text: str) -> list[float]:
        vocab = ["登录", "认证", "缓存", "性能", "成本", "数据库", "安全", "审计"]
        return [1.0 if w in text else 0.0 for w in vocab]


def test_cosine_similarity():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([0, 0], [0, 0]) == 0.0


def test_exact_hit_preferred_over_semantic():
    cache = SemanticCache(ContractBoundCache(), embedder=FakeEmbedder())
    c = expert_contract("expert_a")
    cache.put(c, "登录认证怎么设计", None, {"v": "exact-q"})
    value, kind = cache.get(c, "登录认证怎么设计", None)
    assert kind == "exact" and value == {"v": "exact-q"}


def test_semantic_hit_within_threshold():
    cache = SemanticCache(ContractBoundCache(), embedder=FakeEmbedder(), threshold=0.8)
    c = expert_contract("expert_a")
    cache.put(c, "登录认证怎么设计", None, {"answer": 42})
    # 未缓存的近似问题 → 语义命中
    value, kind = cache.get(c, "认证登录怎么设计", None, semantic=True)
    assert kind == "semantic" and value == {"answer": 42}
    assert cache.stats.semantic_hits >= 1


def test_semantic_never_crosses_contract():
    cache = SemanticCache(ContractBoundCache(), embedder=FakeEmbedder(), threshold=0.8)
    c1 = expert_contract("expert_a")
    c2 = c1.with_changes(**{"identity.description": "v2"})
    cache.put(c1, "缓存性能怎么优化", None, {"for": "c1"})
    value, kind = cache.get(c2, "缓存性能怎么优化", None, semantic=True)
    assert kind == "miss" and value is None


def test_semantic_respects_evidence_snapshot():
    cache = SemanticCache(ContractBoundCache(), embedder=FakeEmbedder(), threshold=0.8)
    c = expert_contract("expert_a")
    cache.put(c, "登录认证方案", ["doc-A"], {"for": "A"})
    value, kind = cache.get(c, "认证登录方案", ["doc-B"], semantic=True)
    assert kind == "miss" and value is None


def test_threshold_gates_semantic():
    cache = SemanticCache(ContractBoundCache(), embedder=FakeEmbedder(), threshold=0.99)
    c = expert_contract("expert_a")
    cache.put(c, "登录认证", None, {"v": 1})
    value, kind = cache.get(c, "数据库性能", None, semantic=True)
    assert kind == "miss"


def test_semantic_disabled_falls_back_exact_only():
    cache = SemanticCache(ContractBoundCache(), embedder=FakeEmbedder(), enabled=False)
    c = expert_contract("expert_a")
    cache.put(c, "登录认证", None, {"v": 1})
    value, kind = cache.get(c, "认证登录", None, semantic=True)
    assert kind == "miss"  # 仅精确层，语义禁用
    value2, kind2 = cache.get(c, "登录认证", None)
    assert kind2 == "exact"


def test_stats_backward_compatible():
    cache = SemanticCache(ContractBoundCache(), embedder=FakeEmbedder())
    c = expert_contract("expert_a")
    cache.put(c, "登录认证", None, {"v": 1})
    cache.get(c, "登录认证", None)
    cache.get(c, "认证登录", None, semantic=True)
    s = cache.stats
    assert hasattr(s, "hits") and hasattr(s, "hit_rate")  # 兼容 CacheStats
    assert s.semantic_hits >= 1


def test_invalidate_contract_clears_semantic_index():
    cache = SemanticCache(ContractBoundCache(), embedder=FakeEmbedder(), threshold=0.8)
    c = expert_contract("expert_a")
    cache.put(c, "缓存性能", None, {"v": 1})
    cache.invalidate_contract(c)
    value, kind = cache.get(c, "缓存性能怎么优化", None, semantic=True)
    assert kind == "miss"
