"""TC-V2-WS：多 Workspace 隔离。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import expert_contract
from wbr.core.constants import MemoryLayer
from wbr.core.exceptions import AppError
from wbr.core.harness import CaseSuite, GoldenCase
from wbr.app.workspace import WorkspaceRegistry


def test_create_get_list_delete(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    reg.create("team_alpha")
    assert reg.get("team_alpha") is not None
    assert [w.name for w in reg.list()] == ["team_alpha"]
    with pytest.raises(AppError, match="已存在"):
        reg.create("team_alpha")
    reg.delete("team_alpha")
    with pytest.raises(AppError, match="不存在"):
        reg.get("team_alpha")


def test_name_constraints(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    with pytest.raises(AppError, match="名称"):
        reg.create("Bad-Name")
    with pytest.raises(AppError, match="名称"):
        reg.create("x" * 40)


def test_contract_isolation(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    reg.create("ws_a"), reg.create("ws_b")
    reg.registry("ws_a").create(expert_contract("expert_a"))
    assert reg.registry("ws_b").get("expert_a") is None   # B 看不到 A 的契约
    assert reg.registry("ws_a").get("expert_a") is not None
    # A 删不掉 B 的（不存在）
    assert reg.registry("ws_b").delete("expert_a") is False


def test_suite_and_task_isolation(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    reg.create("ws_a"), reg.create("ws_b")
    sa = reg.suite_path("ws_a") / "s1.json"
    CaseSuite(suite_id="s1").save(str(sa))
    assert list(reg.suite_path("ws_a").glob("*.json"))
    assert list(reg.suite_path("ws_b").glob("*.json")) == []  # B 的用例库为空
    ta = reg.task_store("ws_a")
    assert ta.root != reg.task_store("ws_b").root


def test_memory_namespace_isolation(tmp_path):
    from tests.wbr.factories import expert_contract as ec

    reg = WorkspaceRegistry(tmp_path)
    reg.create("ws_a"), reg.create("ws_b")
    hub_a, hub_b = reg.memory_hub("ws_a"), reg.memory_hub("ws_b")
    c = ec("expert_a", read_layers=list(MemoryLayer), write_layers=list(MemoryLayer),
           allow_global_write=True)
    hub_a.write(MemoryLayer.GLOBAL_SHARED, "k", "value-of-A", contract=c)
    assert hub_a.read(MemoryLayer.GLOBAL_SHARED, "k", contract=c) == "value-of-A"
    assert hub_b.read(MemoryLayer.GLOBAL_SHARED, "k", contract=c) is None  # 跨 workspace 不可见


def test_cross_workspace_copy_records_lineage(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    reg.create("ws_a"), reg.create("ws_b")
    src = expert_contract("expert_a")
    reg.registry("ws_a").create(src)
    copied = reg.copy_contract("ws_a", "ws_b", "expert_a")
    assert copied.content_hash == src.content_hash  # 内容一致
    assert copied.meta.changelog                    # 血缘记录在 changelog
    assert "ws_a" in copied.meta.changelog[-1]
    # 目标为独立副本：改 B 不影响 A
    reg.registry("ws_b").update("expert_a", src.with_changes(**{"identity.description": "v2"}))
    assert reg.registry("ws_a").get("expert_a").identity.description != "v2"


def test_copy_missing_contract(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    reg.create("ws_a"), reg.create("ws_b")
    with pytest.raises(AppError):
        reg.copy_contract("ws_a", "ws_b", "ghost")
