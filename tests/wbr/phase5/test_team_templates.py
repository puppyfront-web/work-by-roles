"""TC-5-TPL-1~3：官方模板库加载、完整性与端到端。"""
from __future__ import annotations

import pytest

from wbr.core.contract.models import RoleType
from wbr.core.exceptions import AppError
from wbr.templates.registry import list_teams, load_team, load_team_spec

ALL_TEAMS = ["arch_review_team", "security_audit_team"]


def test_list_teams_contains_two_official():
    names = {t["name"] for t in list_teams()}
    assert {"arch_review_team", "security_audit_team"} <= names


@pytest.mark.parametrize("team", ALL_TEAMS)
def test_team_loads_and_contracts_valid(team):
    contracts = load_team(team)
    assert len(contracts) == 5
    for rid, c in contracts.items():
        assert c.role_id == rid
        assert len(c.content_hash) == 64  # 加载时已定版
        assert c.sop.steps


@pytest.mark.parametrize("team", ALL_TEAMS)
def test_team_structure_completeness(team):
    spec = load_team_spec(team)
    assert spec.coordinator.role_type == RoleType.COORDINATOR
    assert spec.verifier.role_type == RoleType.VERIFIER
    assert len(spec.experts) == 3
    for c in spec.contracts.values():
        # SOP ≥ 3 步、禁区非空、Schema 非空
        assert len(c.sop.steps) >= 3, c.role_id
        assert not c.forbidden.is_empty(), c.role_id
        assert c.output_spec.schema_, c.role_id
        assert c.token_quota.max_turn_tokens > 0
    # verifier 评审维度 ≥ 3
    assert len(spec.verifier.review_criteria.dimensions) >= 3
    # 角色类型正确性互斥
    for c in spec.experts:
        assert c.review_criteria is None


def test_unknown_team_rejected():
    with pytest.raises(AppError, match="不存在"):
        load_team("no_such_team")
    with pytest.raises(AppError):
        load_team_spec("nope")


def test_template_e2e_review_session():
    """TC-5-TPL-3 ★：模板直接驱动会审全流程。"""
    from tests.wbr.fakes import FakeRedis  # noqa: F401 - 确认假件可用
    from wbr.core.audit.trail import AuditTrail
    from wbr.core.orchestration import ReviewSession, ScriptedInvoker

    spec = load_team_spec("arch_review_team")
    scripts = {}
    for rid, c in spec.contracts.items():
        if c.role_type == RoleType.COORDINATOR:
            scripts[rid] = {"assignments": [
                {"expert_role_id": e.role_id, "sub_question": "拆分方案评估"} for e in spec.experts
            ]}
        elif c.role_type == RoleType.VERIFIER:
            scripts[rid] = {"passed": True,
                            "scores": {d.name: 0.8 for d in c.review_criteria.dimensions},
                            "comments": "证据充分，结论一致", "final_answer": "建议按领域拆分"}
        else:
            scripts[rid] = {"conclusion": f"{rid} 支持拆分", "confidence": 0.85,
                            "citations": ["[^1] 基准测试"]}
    audit = AuditTrail()
    session = ReviewSession(
        coordinator_contract=spec.coordinator,
        expert_contracts=spec.experts,
        verifier_contract=spec.verifier,
        invoker=ScriptedInvoker(scripts),
        audit=audit,
    )
    result = session.run("评审：单体拆分为微服务的方案")
    assert result.status.value == "completed"
    assert len(result.expert_outcomes) == 3
    assert result.verifier_verdict.passed is True
    assert audit.events


def test_template_e2e_regression_engine():
    """模板直接驱动 Harness 回归。"""
    from wbr.core.harness import CaseSuite, GoldenCase, RegressionEngine
    from wbr.core.orchestration import ScriptedInvoker

    spec = load_team_spec("security_audit_team")
    scripts = {}
    for rid, c in spec.contracts.items():
        if c.role_type == RoleType.COORDINATOR:
            scripts[rid] = {"assignments": [
                {"expert_role_id": e.role_id, "sub_question": "登录与支付接口审计"} for e in spec.experts
            ]}
        elif c.role_type == RoleType.VERIFIER:
            scripts[rid] = {"passed": True,
                            "scores": {d.name: 0.85 for d in c.review_criteria.dimensions},
                            "comments": "审计覆盖充分", "final_answer": "2 个中危发现需整改"}
        else:
            scripts[rid] = {"findings": [
                {"severity": "medium", "title": f"{rid} 示例发现", "detail": "详情",
                 "location": "svc.py:1", "citations": ["[^1]"]},
            ], "confidence": 0.9}
    engine = RegressionEngine(contracts=dict(spec.contracts), invoker=ScriptedInvoker(scripts))
    suite = CaseSuite(suite_id="sec-suite")
    suite.add(GoldenCase(case_id="pay_audit", question="审计支付接口",
                         expert_role_ids=[e.role_id for e in spec.experts]))
    report = engine.run_suite(suite, stability_runs=2)
    assert report.metrics.overall_pass_rate == 1.0
    assert report.metrics.expert_conclusion_stability == 1.0
