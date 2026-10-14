"""TC-V2.1-CONTRACT：契约增量可选字段（intent_policy / inner_loop）。"""
from __future__ import annotations

import json

from tests.wbr.factories import coordinator_contract, expert_contract
from wbr.core.contract.diff import ChangeCategory, ContractDiffEngine, Severity
from wbr.core.orchestration.intent import IntentPolicy
from wbr.core.orchestration.inner_loop import InnerLoopConfig


def test_old_contract_json_still_loads():
    """旧契约 JSON（无新字段）向后兼容加载。"""
    old = coordinator_contract()
    data = json.loads(old.to_json())
    assert "intent_policy" not in data or data["intent_policy"] is None
    restored = type(old).model_validate(data)
    assert restored.intent_policy is None and restored.inner_loop is None


def test_policy_fields_enter_content_hash():
    """配置即契约：改阈值 = 新哈希 = Diff 可见（规则3/4）。"""
    c1 = coordinator_contract()
    c2 = c1.with_changes(intent_policy=IntentPolicy(confidence_threshold=0.9))
    assert c2.intent_policy is not None
    assert c2.content_hash != c1.content_hash  # 进哈希
    report = ContractDiffEngine().diff(c1, c2)
    assert any(c.category == ChangeCategory.POLICY for c in report.changes)


def test_inner_loop_config_field_and_hash():
    c1 = expert_contract("expert_a")
    c2 = c1.with_changes(inner_loop=InnerLoopConfig(max_rounds=5, loop_quota_tokens=6000))
    assert c2.inner_loop.max_rounds == 5
    assert c2.content_hash != c1.content_hash


def test_policy_serialization_roundtrip():
    c = coordinator_contract().with_changes(intent_policy=IntentPolicy(confidence_threshold=0.8))
    restored = type(c).from_json(c.to_json())
    assert restored.intent_policy.confidence_threshold == 0.8
    assert restored == c
