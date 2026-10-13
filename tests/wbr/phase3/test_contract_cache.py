"""TC-3-CACHE-1~5：契约绑定语义缓存。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import expert_contract
from tests.wbr.fakes import FakeRedis
from wbr.adapters.storage.redis_backend import RedisCacheBackend
from wbr.core.cache import (
    ContractBoundCache,
    InMemoryCacheBackend,
    cache_key,
    evidence_snapshot_id,
    normalize_question,
    question_hash,
)


def test_key_three_factors():
    c = expert_contract("expert_a")
    k_same = cache_key(c, "问题Q", ["doc1"])
    k_same2 = cache_key(c, "问题Q", ["doc1"])
    assert k_same == k_same2
    # 证据不同 → key 不同
    assert cache_key(c, "问题Q", ["doc2"]) != k_same
    # 问题不同 → key 不同
    assert cache_key(c, "问题Q2", ["doc1"]) != k_same
    # 契约不同 → key 不同
    assert cache_key(expert_contract("expert_a").with_changes(**{"identity.description": "v2"}), "问题Q", ["doc1"]) != k_same
    # 无证据 → 固定 "none"
    assert evidence_snapshot_id(None) == "none"
    assert evidence_snapshot_id([]) == "none"


def test_question_normalization_full_half_width():
    assert normalize_question("  ｑｅｒｔ　Q  ") == normalize_question("qert Q")
    assert question_hash("问题１") == question_hash("问题1")


def test_hit_miss_and_stats():
    c = expert_contract("expert_a")
    cache = ContractBoundCache()
    cache.reset_stats()
    assert cache.get(c, "q1") is None
    cache.put(c, "q1", None, {"answer": 42})
    assert cache.get(c, "q1") == {"answer": 42}
    s = cache.stats
    assert (s.hits, s.misses) == (1, 1)
    assert s.hit_rate == pytest.approx(0.5)


def test_enabled_false_passthrough():
    c = expert_contract("expert_a")
    cache = ContractBoundCache(enabled=False)
    cache.put(c, "q", None, {"x": 1})
    assert cache.get(c, "q") is None
    assert cache.stats.misses >= 1


def test_invalidate_on_contract_change_active_and_passive():
    c1 = expert_contract("expert_a")
    cache = ContractBoundCache()
    cache.put(c1, "q", None, {"v": 1})
    assert cache.get(c1, "q") == {"v": 1}

    # 被动防线：Key 三要素使新契约无法命中旧条目（脏数据绝不返回）
    c2 = c1.with_changes(**{"identity.description": "v2"})
    assert cache.get(c2, "q") is None
    # 深度防线：即使后端条目哈希被篡改，被动校验也丢弃并计失效
    from wbr.core.cache.contract_cache import cache_key as _ck

    entry = cache._backend.get(_ck(c1, "q", None))
    entry["contract_hash"] = "tampered"
    cache._backend.set(_ck(c1, "q", None), entry)
    assert cache.get(c1, "q") is None
    assert cache.stats.invalidations >= 1

    # 主动失效：同契约新值 + invalidate 后不可见
    cache2 = ContractBoundCache()
    cache2.put(c1, "q", None, {"v": 2})
    assert cache2.invalidate_contract(c1) >= 1
    assert cache2.get(c1, "q") is None


def test_no_cross_pollination():
    """相同契约+问题但证据不同 / 不同问题：绝不返回他人条目。"""
    c = expert_contract("expert_a")
    cache = ContractBoundCache()
    cache.put(c, "q1", ["evidence-A"], {"for": "A"})
    assert cache.get(c, "q1", ["evidence-A"]) == {"for": "A"}
    assert cache.get(c, "q1", ["evidence-B"]) is None
    assert cache.get(c, "q2", ["evidence-A"]) is None


def test_lru_eviction():
    backend = InMemoryCacheBackend(max_entries=2)
    cache = ContractBoundCache(backend)
    c = expert_contract("expert_a")
    cache.put(c, "q1", None, {"v": 1})
    cache.put(c, "q2", None, {"v": 2})
    cache.get(c, "q1")  # 触碰 q1
    cache.put(c, "q3", None, {"v": 3})  # 驱逐最久未用的 q2
    assert cache.get(c, "q2") is None
    assert cache.get(c, "q1") == {"v": 1}
    assert cache.get(c, "q3") == {"v": 3}
    assert cache.stats.evictions >= 1


def test_redis_cache_backend_bridge():
    backend = RedisCacheBackend(FakeRedis())
    cache = ContractBoundCache(backend)
    c = expert_contract("expert_a")
    cache.put(c, "问题", None, {"v": "redis"})
    assert cache.get(c, "问题") == {"v": "redis"}
    assert cache.get(expert_contract("expert_a").with_changes(**{"identity.description": "v9"}), "问题") is None
    assert cache.invalidate_contract(c) >= 1
    assert cache.get(c, "问题") is None


def test_question_hash_deterministic():
    assert question_hash("q") == question_hash("q")
    assert question_hash("q") == question_hash("  q  ")  # 首尾空白被规范化
    assert question_hash("ｑ") == question_hash("q")     # 全半角归一
    assert question_hash("q1") != question_hash("q2")
