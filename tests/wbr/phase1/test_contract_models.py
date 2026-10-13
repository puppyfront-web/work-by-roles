"""TC-1-CONTRACT-1~5：RoleContract 模型行为。"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from tests.wbr.factories import coordinator_contract, expert_contract, verifier_contract
from wbr.core.constants import MemoryLayer
from wbr.core.contract.models import (
    ReviewCriteria,
    ReviewDimension,
    RoleContract,
    Sop,
    SopStep,
    TokenQuota,
)


def test_build_hash_and_determinism():
    c1 = expert_contract("expert_a")
    c2 = expert_contract("expert_a")
    assert c1.content_hash == c2.content_hash
    assert len(c1.content_hash) == 64
    int(c1.content_hash, 16)


def test_hash_changes_on_any_business_field():
    c = expert_contract("expert_a")
    changed = c.with_changes(**{"identity.description": "改动描述"})
    assert changed.content_hash != c.content_hash
    changed2 = c.with_changes(forbidden={"behaviors": ["x"]})
    assert changed2.content_hash != c.content_hash
    # meta 变更不影响内容哈希
    same = c.with_changes(bump="minor")
    assert same.content_hash == c.content_hash


def test_json_roundtrip_lossless():
    c = expert_contract(
        "expert_a",
        forbidden=None,
        evidence=None,
        read_layers=[MemoryLayer.ROLE_SESSION],
        tools=["search"],
    )
    restored = RoleContract.from_json(c.to_json())
    assert restored == c
    assert restored.content_hash == c.content_hash


def test_save_load_roundtrip(tmp_path):
    c = expert_contract("expert_a")
    p = tmp_path / "c.json"
    c.save(str(p))
    loaded = RoleContract.load(str(p))
    assert loaded == c
    assert json.loads(p.read_text())["identity"]["role_id"] == "expert_a"


def test_cross_field_rules():
    with pytest.raises(ValidationError, match="review_criteria"):
        RoleContract.model_validate({
            **verifier_contract().model_dump(by_alias=True),
            "review_criteria": None,
        })
    with pytest.raises(ValidationError, match="Coordinator"):
        data = coordinator_contract().model_dump(by_alias=True)
        data["review_criteria"] = ReviewCriteria(
            dimensions=[ReviewDimension(name="x", weight=0.5, pass_threshold=0.5)],
            overall_pass_threshold=0.6,
        )
        RoleContract.model_validate(data)


def test_with_changes_copy_on_write():
    c = expert_contract("expert_a")
    derived = c.with_changes(**{"identity.description": "v2 描述"}, bump="minor", changelog="放宽描述")
    assert c.identity.description != derived.identity.description
    assert derived.meta.version == "1.1.0"
    assert derived.meta.changelog == ["放宽描述"]
    assert derived.meta.created_at == c.meta.created_at
    assert derived.content_hash != c.content_hash
    # 原实例未被修改
    assert c.meta.version == "1.0.0"


def test_with_changes_unknown_field_rejected():
    c = expert_contract("expert_a")
    with pytest.raises(ValueError, match="未知契约字段"):
        c.with_changes(no_such_field=1)


def test_field_constraints():
    with pytest.raises(ValidationError):
        expert_contract("Bad-ID")  # role_id 正则
    with pytest.raises(ValidationError):
        TokenQuota(max_prompt_tokens=0)  # 配额必须 >0
    with pytest.raises(ValidationError):
        ReviewDimension(name="d", weight=1.5, pass_threshold=0.5)  # weight ∈ (0,1]
    with pytest.raises(ValidationError):
        Sop(steps=[
            SopStep(step_id="s", title="t", instruction="i"),
            SopStep(step_id="s", title="t2", instruction="i2"),
        ])  # step_id 唯一
    with pytest.raises(ValidationError):
        Sop(steps=[])  # SOP 至少一步


def test_all_denied_tool_policy():
    c = expert_contract("expert_a")
    assert c.tool_policy.all_denied is True
    c2 = expert_contract("expert_a", tools=["search"])
    assert c2.tool_policy.all_denied is False


def test_verifier_builder_has_criteria():
    v = verifier_contract()
    assert v.role_type.value == "verifier"
    assert v.review_criteria is not None
    assert v.review_criteria.overall_pass_threshold == 0.6
