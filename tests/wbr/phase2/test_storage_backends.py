"""TC-2-STO-1~3：存储后端协议一致性 + 记忆隔离 + Redis 键编码。"""
from __future__ import annotations

import os

import pytest

from tests.wbr.fakes import FakeRedis
from wbr.adapters.storage.memory_backend import InMemoryStorageBackend
from wbr.adapters.storage.redis_backend import RedisStorageBackend
from wbr.adapters.storage.store import StorageBackedMemoryStore, persistent_memory_hub
from wbr.core.constants import MemoryLayer
from wbr.core.memory.base import MemoryRecord
from wbr.core.memory.hub import MemoryHub

BACKENDS = {
    "memory": lambda: InMemoryStorageBackend(),
    "redis(fake)": lambda: RedisStorageBackend(FakeRedis()),
}


# ---- 协议一致性（双后端参数化） ----
@pytest.mark.parametrize("backend_name", BACKENDS.keys())
def test_backend_protocol(backend_name):
    backend = BACKENDS[backend_name]()
    ns = ("role_session", "role_session:e1:s1")
    assert backend.get(ns, "k") is None
    backend.set(ns, "k", {"a": 1})
    assert backend.get(ns, "k") == {"a": 1}
    backend.append(ns, "log", "x")
    backend.append(ns, "log", "y")
    assert backend.get(ns, "k") == {"a": 1}  # append 不影响 get 最新值语义
    assert backend.keys(ns) == ["k", "log"]
    backend.delete(ns, "k")
    assert backend.keys(ns) == ["log"]
    backend.clear(ns)
    assert backend.keys(ns) == []


@pytest.mark.parametrize("backend_name", BACKENDS.keys())
def test_memory_isolation_four_layers_two_backends(backend_name):
    """TC-2-STO-2 ★：4 层 × 双后端，同 key 不同 role/session 互不可见。"""
    hub = MemoryHub(StorageBackedMemoryStore(BACKENDS[backend_name]()))
    from tests.wbr.factories import expert_contract

    c1 = expert_contract("expert_a", read_layers=list(MemoryLayer), write_layers=list(MemoryLayer),
                         allow_global_write=True)
    c2 = expert_contract("expert_b", read_layers=list(MemoryLayer), write_layers=list(MemoryLayer),
                         allow_global_write=True)
    for layer in MemoryLayer:
        hub.write(layer, "secret", f"v-{layer.value}", contract=c1, session_id="s1")
    for layer in MemoryLayer:
        got = hub.read(layer, "secret", contract=c2, session_id="s1")
        if layer == MemoryLayer.GLOBAL_SHARED:
            assert got == "v-global_shared"
        elif layer == MemoryLayer.TASK_SCRATCH:
            assert got == "v-task_scratch"  # 任务级：同会话跨角色可见
        else:
            assert got is None  # 角色私有层完全隔离
        # 同角色不同会话
        if layer in (MemoryLayer.ROLE_SESSION, MemoryLayer.TASK_SCRATCH):
            assert hub.read(layer, "secret", contract=c1, session_id="s2") is None


def test_memory_record_roundtrip_through_backend():
    """记录经 JSON 序列化往返后语义不变。"""
    store = StorageBackedMemoryStore(RedisStorageBackend(FakeRedis()))
    ns = (MemoryLayer.ROLE_STATIC.value, "role_static:e1")
    rec = MemoryRecord(key="prefs", value={"tone": "严谨"}, layer=MemoryLayer.ROLE_STATIC, role_id="e1")
    store.set(ns, "prefs", rec)
    loaded = store.get(ns, "prefs")
    assert loaded == rec
    assert loaded.value == {"tone": "严谨"}


def test_redis_key_encoding_and_ttl():
    client = FakeRedis()
    backend = RedisStorageBackend(client, default_ttl=60)
    ns = ("role_session", "role_session:e1:s1")
    backend.set(ns, "k", "v")
    raw_keys = client.keys("wbr:role_session:role_session:e1:s1:*")
    assert raw_keys == ["wbr:role_session:role_session:e1:s1:k"]
    assert client.ttl_of("wbr:role_session:role_session:e1:s1:k") == 60
    backend.set(ns, "k2", "v", ttl=None)  # 显式 None → 仍走 default_ttl
    # 剥离前缀后取键名
    assert backend.keys(ns) == ["k", "k2"]


def test_redis_real_server_gated():
    """真实 Redis 集成测试：仅当 WBR_TEST_REDIS 设置时执行。"""
    url = os.environ.get("WBR_TEST_REDIS")
    if not url:
        pytest.skip("未设置 WBR_TEST_REDIS，跳过真实 Redis 集成测试")
    import redis as redis_lib

    client = redis_lib.Redis.from_url(url, decode_responses=True)
    backend = RedisStorageBackend(client)
    ns = ("task_scratch", "task_scratch:t:integration")
    backend.set(ns, "ping", {"ok": True})
    assert backend.get(ns, "ping") == {"ok": True}


def test_persistent_memory_hub_factory():
    hub = persistent_memory_hub(InMemoryStorageBackend())
    assert isinstance(hub, MemoryHub)
