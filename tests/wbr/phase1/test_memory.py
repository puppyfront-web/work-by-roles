"""TC-1-MEM-1~3：四层隔离记忆与权限。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import expert_contract
from wbr.core.audit.models import AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.constants import MemoryLayer
from wbr.core.exceptions import MemoryPermissionDeniedError
from wbr.core.memory.base import InMemoryMemoryStore
from wbr.core.memory.hub import MemoryHub

L4 = list(MemoryLayer)


def make_hub(**kw) -> tuple[MemoryHub, object]:
    contract = expert_contract(
        "expert_a",
        read_layers=kw.get("read_layers", [MemoryLayer.ROLE_SESSION, MemoryLayer.TASK_SCRATCH]),
        write_layers=kw.get("write_layers", [MemoryLayer.ROLE_SESSION, MemoryLayer.TASK_SCRATCH]),
        allow_global_write=kw.get("allow_global_write", False),
    )
    hub = MemoryHub(audit=kw.get("audit"))
    return hub, contract


@pytest.mark.parametrize("layer", L4, ids=[l.value for l in L4])
def test_layer_isolation(layer):
    hub, c = make_hub(read_layers=L4, write_layers=L4, allow_global_write=True)
    sid = "s1"
    # 同 key 同层写入后，其他层读不到
    hub.write(layer, "k", f"v-{layer.value}", contract=c, session_id=sid)
    for other in L4:
        if other == layer:
            assert hub.read(other, "k", contract=c, session_id=sid) == f"v-{layer.value}"
        else:
            assert hub.read(other, "k", contract=c, session_id=sid) is None


@pytest.mark.parametrize("layer", L4, ids=[l.value for l in L4])
def test_role_and_session_isolation(layer):
    hub, c = make_hub(read_layers=L4, write_layers=L4, allow_global_write=True)
    ca = expert_contract("expert_b", read_layers=L4, write_layers=L4, allow_global_write=True)
    hub.write(layer, "k", "a-value", contract=c, session_id="s1")
    # 不同角色
    if layer in (MemoryLayer.ROLE_STATIC, MemoryLayer.ROLE_SESSION):
        assert hub.read(layer, "k", contract=ca, session_id="s1") is None
    else:  # TASK_SCRATCH 任务级（同会话跨角色可见）、GLOBAL_SHARED 全局
        assert hub.read(layer, "k", contract=ca, session_id="s1") == "a-value"
    # 同角色不同会话
    if layer in (MemoryLayer.ROLE_SESSION, MemoryLayer.TASK_SCRATCH):
        assert hub.read(layer, "k", contract=c, session_id="s2") is None
    else:
        assert hub.read(layer, "k", contract=c, session_id="s2") == "a-value"


def test_permission_denied_read_and_write():
    hub, c = make_hub(read_layers=[MemoryLayer.ROLE_SESSION], write_layers=[MemoryLayer.ROLE_SESSION])
    with pytest.raises(MemoryPermissionDeniedError):
        hub.read(MemoryLayer.ROLE_STATIC, "k", contract=c)
    with pytest.raises(MemoryPermissionDeniedError):
        hub.write(MemoryLayer.GLOBAL_SHARED, "k", "v", contract=c)


def test_global_write_requires_second_gate():
    hub, c = make_hub(
        read_layers=[MemoryLayer.GLOBAL_SHARED],
        write_layers=[MemoryLayer.GLOBAL_SHARED],
        allow_global_write=False,
    )
    with pytest.raises(MemoryPermissionDeniedError):
        hub.write(MemoryLayer.GLOBAL_SHARED, "k", "v", contract=c)
    hub2, c2 = make_hub(
        read_layers=[MemoryLayer.GLOBAL_SHARED],
        write_layers=[MemoryLayer.GLOBAL_SHARED],
        allow_global_write=True,
    )
    hub2.write(MemoryLayer.GLOBAL_SHARED, "k", "v", contract=c2)
    assert hub2.read(MemoryLayer.GLOBAL_SHARED, "k", contract=c2) == "v"


def test_denied_access_audited():
    trail = AuditTrail()
    hub, c = make_hub(read_layers=[MemoryLayer.ROLE_SESSION], write_layers=[], audit=trail)
    with pytest.raises(MemoryPermissionDeniedError):
        hub.read(MemoryLayer.ROLE_STATIC, "k1", contract=c)
    with pytest.raises(MemoryPermissionDeniedError):
        hub.write(MemoryLayer.ROLE_SESSION, "k2", "v", contract=c)
    events = [e for e in trail.events if e.event_type == AuditEventType.MEMORY_ACCESS]
    assert len(events) == 2
    assert all(e.payload["allowed"] is False for e in events)
    allowed_ev = hub  # 读写成功也留痕
    hub.read(MemoryLayer.ROLE_SESSION, "ok", contract=c)
    events = [e for e in trail.events if e.event_type == AuditEventType.MEMORY_ACCESS]
    assert events[-1].payload["allowed"] is True


def test_append_and_keys():
    hub, c = make_hub(read_layers=L4, write_layers=L4, allow_global_write=True)
    hub.append(MemoryLayer.TASK_SCRATCH, "log", "a", contract=c, session_id="s1")
    hub.append(MemoryLayer.TASK_SCRATCH, "log", "b", contract=c, session_id="s1")
    assert hub.read(MemoryLayer.TASK_SCRATCH, "log", contract=c, session_id="s1") == ["a", "b"]
    assert hub.keys_of(MemoryLayer.TASK_SCRATCH, contract=c, session_id="s1") == ["log"]


def test_custom_store_backend_used():
    store = InMemoryMemoryStore()
    hub = MemoryHub(store)
    assert hub.store is store


def test_store_delete_clear_and_nonlist_append():
    store = InMemoryMemoryStore()
    from wbr.core.memory.base import MemoryRecord

    ns = (MemoryLayer.ROLE_SESSION.value, "role_session:e1:s1")
    store.set(ns, "k", MemoryRecord(key="k", value="v", layer=MemoryLayer.ROLE_SESSION))
    assert store.get(ns, "k").value == "v"
    assert store.keys(ns) == ["k"]
    # append 到标量值 → 包装为列表
    store.append(ns, "k", "x")
    assert store.get(ns, "k").value == ["v", "x"]
    # append 到不存在的键 → 新建列表
    store.append(ns, "new", 1)
    assert store.get(ns, "new").value == [1]
    store.delete(ns, "k")
    assert store.get(ns, "k") is None
    store.clear(ns)
    assert store.keys(ns) == []


def test_trail_tree_and_dict():
    from wbr.core.audit.models import AuditEvent, AuditEventType
    from wbr.core.audit.trail import AuditTrail

    trail = AuditTrail()
    trail.append(AuditEvent(event_type=AuditEventType.SESSION_STARTED, trace_id="t1"))
    trail.append(AuditEvent(event_type=AuditEventType.EXPERT_STARTED, trace_id="t1", role_id="e1"))
    tree = trail.tree("t1")
    assert tree.trace_id == "t1"
    assert [n.event_type for n in tree.nodes] == [
        AuditEventType.SESSION_STARTED, AuditEventType.EXPERT_STARTED
    ]
    empty = trail.tree("nope")
    assert empty.nodes == []
    d = trail.to_dict()
    assert d["events"] and d["behaviors"] == []
