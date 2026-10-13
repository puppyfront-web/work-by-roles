"""TC-1-DIFF-1~3：契约版本 Diff 引擎。"""
from __future__ import annotations

import json

from tests.wbr.factories import expert_contract
from wbr.core.contract.diff import ChangeCategory, ChangeType, ContractDiffEngine, Severity
from wbr.core.contract.models import ForbiddenRule, SopStep


def test_rule_change_on_sop():
    old = expert_contract("expert_a")
    new = old.with_changes(
        sop={"steps": [
            {"step_id": "analyze", "title": "分析", "instruction": "分析子问题并给出结论（修订）"},
            {"step_id": "conclude", "title": "结论", "instruction": "按 Schema 输出结论"},
        ]},
        changelog="修订分析步骤",
    )
    report = ContractDiffEngine().diff(old, new)
    sop_changes = [c for c in report.changes if c.category == ChangeCategory.RULE]
    assert sop_changes and sop_changes[0].change_type == ChangeType.MODIFIED
    assert sop_changes[0].severity == Severity.MEDIUM
    assert "analyze" in sop_changes[0].path  # 按 step_id 对齐


def test_schema_required_removal_is_breaking():
    old = expert_contract("expert_a")
    tighter = dict(old.output_spec.schema_)
    tighter["required"] = ["conclusion", "confidence", "citations"]
    new = old.with_changes(output_spec={"schema": tighter, "strict": True})
    report = ContractDiffEngine().diff(old, new)
    sc = [c for c in report.changes if c.category == ChangeCategory.SCHEMA]
    assert sc
    assert report.has_breaking is True
    assert any(c.severity == Severity.HIGH for c in sc)


def test_forbidden_relaxation_high():
    from wbr.core.contract.models import ForbiddenRule as FR

    old = expert_contract("expert_a", forbidden=FR(behaviors=["行为A", "行为B"]))
    new = old.with_changes(forbidden={"behaviors": ["行为A"]})  # 放宽：删除行为B
    report = ContractDiffEngine().diff(old, new)
    forb = [c for c in report.changes if c.category == ChangeCategory.FORBIDDEN]
    assert forb and forb[0].change_type == ChangeType.REMOVED
    assert forb[0].severity == Severity.HIGH
    assert report.has_breaking


def test_policy_whitelist_expansion_high():
    old = expert_contract("expert_a")
    new = old.with_changes(tool_policy={"whitelist": ["search"], "deny_by_default": True})
    report = ContractDiffEngine().diff(old, new)
    pol = [c for c in report.changes if c.category == ChangeCategory.POLICY]
    assert pol and pol[0].severity == Severity.HIGH


def test_field_change_low_no_breaking():
    old = expert_contract("expert_a")
    new = old.with_changes(**{"identity.description": "仅描述变化"})
    report = ContractDiffEngine().diff(old, new)
    assert report.changes
    assert all(c.category == ChangeCategory.FIELD for c in report.changes)
    assert report.has_breaking is False


def test_added_and_removed_steps_aligned():
    old = expert_contract("expert_a")
    steps = [
        {"step_id": "analyze", "title": "分析", "instruction": "分析子问题并给出结论"},
        {"step_id": "conclude", "title": "结论", "instruction": "按 Schema 输出结论"},
        {"step_id": "verify_self", "title": "自检", "instruction": "自检结论"},
    ]
    new = old.with_changes(sop={"steps": steps})
    report = ContractDiffEngine().diff(old, new)
    added = [c for c in report.changes if c.change_type == ChangeType.ADDED]
    assert added and "verify_self" in added[0].path


def test_report_serializable():
    old = expert_contract("expert_a")
    new = old.with_changes(**{"identity.description": "x"})
    d = ContractDiffEngine().diff(old, new).to_dict()
    json.dumps(d, ensure_ascii=False)
    assert d["from_version"] == "1.0.0"


def test_forbidden_behavior_replaced_is_remove_add_pair():
    old = expert_contract("expert_a", forbidden=ForbiddenRule(behaviors=["行为A"]))
    new = old.with_changes(forbidden={"behaviors": ["行为A修订版"]})
    report = ContractDiffEngine().diff(old, new)
    forb = [c for c in report.changes if c.category == ChangeCategory.FORBIDDEN]
    types = {c.change_type for c in forb}
    assert types == {ChangeType.REMOVED, ChangeType.ADDED}
    assert report.has_breaking  # 删除禁区条目 = 放宽 = HIGH
