"""TC-5-TPL-1~3：官方模板库加载、完整性与端到端。"""
from __future__ import annotations

import pytest

from wbr.core.contract.models import RoleType
from wbr.core.exceptions import AppError
from wbr.templates.registry import list_teams, load_team, load_team_spec

ALL_TEAMS = ["arch_review_team", "security_audit_team", "content_review_team"]


def test_list_teams_contains_two_official():
    names = {t["name"] for t in list_teams()}
    assert {"arch_review_team", "security_audit_team", "content_review_team"} <= names


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


def _content_team_scripts(spec, *, cross_question: str | None = None) -> dict:
    """内容团队脚本：按各专家输出 Schema 的形状回放，保证 Schema 门禁全通过。"""
    scripts = {}
    for rid, c in spec.contracts.items():
        if c.role_type == RoleType.COORDINATOR:
            assignments = [{"expert_role_id": e.role_id, "sub_question": f"评审: {e.role_id}"}
                           for e in spec.experts]
            if cross_question:
                # 交叉分派：事实核查与转化力专家回答同一子问题（触发分歧检测分组）
                pair = [rid2 for rid2 in ("fact_checker", "conversion_expert") if rid2 in spec.contracts]
                assignments = [a for a in assignments if a["expert_role_id"] not in pair]
                assignments += [{"expert_role_id": rid2, "sub_question": cross_question} for rid2 in pair]
            scripts[rid] = {"assignments": assignments, "strategy": "parallel"}
        elif c.role_type == RoleType.VERIFIER:
            scripts[rid] = {"passed": True,
                            "scores": {d.name: 0.8 for d in c.review_criteria.dimensions},
                            "comments": "三方发现互证充分", "final_answer": "需修改后发布：弱化涨粉承诺"}
        else:
            base = {"conclusion": f"{rid} 关于内容的评审结论", "confidence": 0.85,
                    "citations": ["[^1] 原文第 1 段"]}
            if rid == "fact_checker":
                payload = {"claims": [
                    {"claim": "3 天涨粉 1 万", "verdict": "exaggerated", "reason": "缺少可复现条件"},
                ], **base}
            elif rid == "platform_compliance":
                payload = {"violations": [
                    {"severity": "medium", "rule": "夸大宣传", "excerpt": "轻松搞定",
                     "suggestion": "补充真实周期与前提"},
                ], **base}
            else:
                payload = {"scores": {"钩子": 0.9, "结构": 0.7, "行动引导": 0.6},
                           "rewrite_suggestions": ["开头直接给结果截图"], **base}
            scripts[rid] = payload
    return scripts


def test_content_review_team_e2e_schema_shapes():
    """内容团队端到端：各专家按其契约 Schema 形状作答，Schema 门禁零违例。"""
    from wbr.core.audit.trail import AuditTrail
    from wbr.core.orchestration import ExpertStatus, ReviewSession, ScriptedInvoker

    spec = load_team_spec("content_review_team")
    session = ReviewSession(
        coordinator_contract=spec.coordinator,
        expert_contracts=spec.experts,
        verifier_contract=spec.verifier,
        invoker=ScriptedInvoker(_content_team_scripts(spec)),
        audit=AuditTrail(),
    )
    result = session.run("评审这篇小红书文案：3天涨粉1万，轻松搞定")
    assert result.status.value == "completed"
    assert len(result.expert_outcomes) == 3
    for outcome in result.expert_outcomes:
        assert outcome.status == ExpertStatus.COMPLETED, outcome.role_id
        assert not outcome.violations, (outcome.role_id, outcome.violations)
    assert result.verifier_verdict.passed is True
    assert "需修改后发布" in result.final_answer


def test_content_review_team_cross_review_disagreement():
    """交叉分派同一子问题给两位专家，结论不同时分歧应被留存（不仲裁）。"""
    from wbr.core.audit.trail import AuditTrail
    from wbr.core.orchestration import ReviewSession, ScriptedInvoker

    spec = load_team_spec("content_review_team")
    scripts = _content_team_scripts(spec, cross_question="核心卖点「3天涨粉1万」是否成立")
    # 人为制造立场分歧：转化力专家认为卖点成立，事实核查专家判定夸大
    scripts["conversion_expert"]["conclusion"] = "卖点成立，保留可提升点击率"
    scripts["fact_checker"]["conclusion"] = "主张夸大，不可验证，建议改写"
    session = ReviewSession(
        coordinator_contract=spec.coordinator,
        expert_contracts=spec.experts,
        verifier_contract=spec.verifier,
        invoker=ScriptedInvoker(scripts),
        audit=AuditTrail(),
    )
    result = session.run("评审小红书涨粉文案")
    assert result.status.value == "completed"
    assert len(result.disagreements) == 1
    disagreement = result.disagreements[0]
    assert set(disagreement.between) == {"conversion_expert", "fact_checker"}
    assert {p["conclusion"] for p in disagreement.positions} == {
        "卖点成立，保留可提升点击率", "主张夸大，不可验证，建议改写"}
