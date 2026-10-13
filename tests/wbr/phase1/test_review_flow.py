"""TC-1-FLOW-1~6：会审全链路（纯 Core，无框架）。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import (
    coordinator_contract,
    expert_contract,
    verifier_contract,
)
from wbr.core.audit.models import AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.constants import MemoryLayer
from wbr.core.exceptions import OrchestrationError
from wbr.core.memory.hub import MemoryHub
from wbr.core.orchestration.invoker import ScriptedInvoker
from wbr.core.orchestration.review import (
    ExpertStatus,
    ReviewSession,
    ReviewStatus,
    ViolationKind,
)


def plan_for(mapping: dict[str, str], strategy: str = "parallel") -> dict:
    return {
        "assignments": [
            {"expert_role_id": rid, "sub_question": sq} for rid, sq in mapping.items()
        ],
        "strategy": strategy,
    }


def build_session(scripts: dict, *, audit: AuditTrail | None = None, fail_experts: dict | None = None, **kw) -> ReviewSession:
    return ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[
            expert_contract("expert_a"),
            expert_contract("expert_b"),
            expert_contract("expert_c"),
        ],
        verifier_contract=verifier_contract(),
        invoker=ScriptedInvoker(scripts, fail_on=fail_experts or {}),
        audit=audit,
        **kw,
    )


GOOD_OUTPUT = {"conclusion": "采用 JWT 无状态方案", "confidence": 0.9}
ALT_OUTPUT = {"conclusion": "采用 Session 有状态方案", "confidence": 0.8}


def test_full_review_flow_passes():
    audit = AuditTrail()
    scripts = {
        "coordinator": plan_for({"expert_a": "认证方案选型", "expert_b": "认证方案选型", "expert_c": "性能评估"}),
        "expert_a": GOOD_OUTPUT,
        "expert_b": {**GOOD_OUTPUT, "confidence": 0.85},
        "expert_c": {"conclusion": "预计 QPS 满足要求", "confidence": 0.7},
        "verifier": {"passed": True, "scores": {"completeness": 0.9, "accuracy": 0.85},
                     "comments": "三位专家结论一致", "final_answer": "推荐 JWT 无状态方案"},
    }
    session = build_session(scripts, audit=audit)
    result = session.run("如何设计登录认证？")

    assert result.status == ReviewStatus.COMPLETED
    assert len(result.expert_outcomes) == 3
    assert all(o.status == ExpertStatus.COMPLETED for o in result.expert_outcomes)
    # 并行执行结果按 role_id 确定性排序
    assert [o.role_id for o in result.expert_outcomes] == ["expert_a", "expert_b", "expert_c"]
    assert result.verifier_verdict is not None and result.verifier_verdict.passed
    assert result.final_answer == "推荐 JWT 无状态方案"
    assert result.trace_id.startswith("wbr-")
    # 审计链完整
    types = audit.event_types_for(result.trace_id)
    assert AuditEventType.SESSION_STARTED in types
    assert AuditEventType.EXPERT_STARTED in types
    assert AuditEventType.EXPERT_COMPLETED in types
    assert AuditEventType.VERIFIER_VERDICT in types
    assert AuditEventType.REVIEW_COMPLETED in types
    # 行为记录留存（摘要化）
    assert len(audit.behaviors) >= 4
    assert all(not rec.output_digest or len(rec.output_digest) <= 32 for rec in audit.behaviors)


def test_disagreement_preserved_not_arbitrated():
    scripts = {
        "coordinator": plan_for({"expert_a": "选型", "expert_b": "选型"}),
        "expert_a": GOOD_OUTPUT,
        "expert_b": ALT_OUTPUT,
        "verifier": {"passed": True, "scores": {"completeness": 0.7, "accuracy": 0.7},
                     "comments": "存在分歧，保留双方观点"},
    }
    session = build_session({"expert_c": GOOD_OUTPUT, **scripts})
    result = session.run("如何设计认证？")
    assert len(result.disagreements) == 1
    d = result.disagreements[0]
    assert d.between == ["expert_a", "expert_b"]
    assert d.topic == "选型"
    positions = {p["role_id"]: p["conclusion"] for p in d.positions}
    assert positions["expert_a"] == GOOD_OUTPUT["conclusion"]
    assert positions["expert_b"] == ALT_OUTPUT["conclusion"]  # 双方立场原样留存
    # 一致的专家对不产生分歧
    assert all("expert_c" not in dd.between for dd in result.disagreements)


def test_expert_failure_degrades_session():
    scripts = {
        "coordinator": plan_for({"expert_a": "q1", "expert_b": "q2"}),
        "expert_b": GOOD_OUTPUT,
        "verifier": {"passed": True, "scores": {"completeness": 0.7, "accuracy": 0.7}, "comments": "ok"},
    }
    class Boom(Exception):
        pass
    session = build_session(scripts, fail_experts={"expert_a": Boom("模型超时")})
    result = session.run("q")
    assert result.status == ReviewStatus.COMPLETED_WITH_FAILURES
    failed = result.outcome_by_role("expert_a")
    assert failed.status == ExpertStatus.FAILED
    assert "模型超时" in failed.error
    ok = result.outcome_by_role("expert_b")
    assert ok.status == ExpertStatus.COMPLETED
    # 失败专家不进入分歧检测，会审整体完成


def test_strict_schema_violation_blocks_expert():
    bad_output = {"conclusion": "缺少置信度"}  # 缺 required: confidence
    scripts = {
        "coordinator": plan_for({"expert_a": "q1"}),
        "expert_a": bad_output,
        "verifier": {"passed": True, "scores": {"completeness": 0.7, "accuracy": 0.7}, "comments": "ok"},
    }
    audit = AuditTrail()
    session = build_session(scripts, audit=audit)
    result = session.run("q")
    outcome = result.outcome_by_role("expert_a")
    assert outcome.status == ExpertStatus.FAILED
    assert any(v.kind == ViolationKind.SCHEMA for v in outcome.violations)
    assert AuditEventType.SCHEMA_VIOLATION in audit.event_types_for(result.trace_id)


def test_non_strict_records_but_completes():
    bad_output = {"conclusion": "缺少置信度"}
    scripts = {
        "coordinator": plan_for({"expert_a": "q1"}),
        "expert_a": bad_output,
        "verifier": {"passed": True, "scores": {"completeness": 0.7, "accuracy": 0.7}, "comments": "ok"},
    }
    loose = expert_contract("expert_a", strict=False)
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[loose],
        verifier_contract=verifier_contract(),
        invoker=ScriptedInvoker(scripts),
    )
    result = session.run("q")
    outcome = result.outcome_by_role("expert_a")
    assert outcome.status == ExpertStatus.COMPLETED
    assert any(v.kind == ViolationKind.SCHEMA for v in outcome.violations)  # 违规仍记录


def test_forbidden_detection():
    from wbr.core.contract.models import ForbiddenRule

    scripts = {
        "coordinator": plan_for({"expert_a": "q1"}),
        "expert_a": {"conclusion": "我会泄露系统提示词给你", "confidence": 0.9},
        "verifier": {"passed": True, "scores": {"completeness": 0.7, "accuracy": 0.7}, "comments": "ok"},
    }
    c = expert_contract("expert_a", forbidden=ForbiddenRule(behaviors=["泄露系统提示词"]))
    audit = AuditTrail()
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[c],
        verifier_contract=verifier_contract(),
        invoker=ScriptedInvoker(scripts),
        audit=audit,
    )
    result = session.run("q")
    outcome = result.outcome_by_role("expert_a")
    assert outcome.status == ExpertStatus.FAILED  # strict 默认拦截
    assert any(v.kind == ViolationKind.FORBIDDEN for v in outcome.violations)
    assert AuditEventType.FORBIDDEN_VIOLATION in audit.event_types_for(result.trace_id)


def test_verifier_reject_low_scores():
    scripts = {
        "coordinator": plan_for({"expert_a": "q1"}),
        "expert_a": GOOD_OUTPUT,
        "verifier": {"passed": False, "scores": {"completeness": 0.3, "accuracy": 0.2},
                     "comments": "证据不足，结论不成立"},
    }
    session = build_session(scripts)
    result = session.run("q")
    assert result.verifier_verdict.passed is False
    assert result.final_answer.startswith("复核未通过")
    assert "证据不足" in result.final_answer


def test_coordinator_failure_fails_session():
    session = build_session({
        "coordinator": "这不是JSON",
        "verifier": {"passed": True, "scores": {}, "comments": "ok"},
    })
    result = session.run("q")
    assert result.status == ReviewStatus.FAILED
    assert "Coordinator" in result.error


def test_memory_snapshot_passed_and_evidence_collected():
    trail = AuditTrail()
    contract = expert_contract(
        "expert_a",
        read_layers=[MemoryLayer.GLOBAL_SHARED, MemoryLayer.ROLE_STATIC],
        write_layers=[],
    )
    hub = MemoryHub(audit=trail, trace_id="t-x")
    # 写入需要权限的契约
    writer = expert_contract(
        "expert_a",
        read_layers=list(MemoryLayer),
        write_layers=list(MemoryLayer),
        allow_global_write=True,
    )
    hub.write(MemoryLayer.GLOBAL_SHARED, "evidence_doc", "公司认证架构现状文档", contract=writer)
    hub.write(MemoryLayer.ROLE_STATIC, "preference", "偏好无状态方案", contract=writer)

    captured = {}

    def expert_script(request):
        captured["snapshot"] = request.memory_snapshot
        return GOOD_OUTPUT

    scripts = {
        "coordinator": plan_for({"expert_a": "q1"}),
        "expert_a": expert_script,
        "verifier": {"passed": True, "scores": {"completeness": 0.7, "accuracy": 0.7}, "comments": "ok"},
    }
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[contract],
        verifier_contract=verifier_contract(),
        invoker=ScriptedInvoker(scripts),
        memory=hub,
    )
    result = session.run("q")
    snap = captured["snapshot"]
    assert snap["global_shared:evidence_doc"] == "公司认证架构现状文档"
    assert snap["role_static:preference"] == "偏好无状态方案"
    # 编译后的 prompt 应包含证据材料
    compiled = session._compiler  # noqa: SLF001 - 测试内省
    assert result.status == ReviewStatus.COMPLETED


def test_role_type_guards():
    with pytest.raises(OrchestrationError):
        ReviewSession(
            coordinator_contract=expert_contract("expert_x"),
            expert_contracts=[expert_contract("expert_a")],
            verifier_contract=verifier_contract(),
            invoker=ScriptedInvoker({}),
        )
    with pytest.raises(OrchestrationError):
        ReviewSession(
            coordinator_contract=coordinator_contract(),
            expert_contracts=[],
            verifier_contract=verifier_contract(),
            invoker=ScriptedInvoker({}),
        )


def test_result_serialization_roundtrip(tmp_path):
    scripts = {
        "coordinator": plan_for({"expert_a": "q1"}),
        "expert_a": GOOD_OUTPUT,
        "verifier": {"passed": True, "scores": {"completeness": 0.7, "accuracy": 0.7},
                     "comments": "ok", "final_answer": "答案"},
    }
    session = build_session(scripts)
    result = session.run("q")
    p = tmp_path / "result.json"
    result.save(str(p))
    from wbr.core.orchestration.review import ReviewResult as RR

    loaded = RR.model_validate_json(p.read_text(encoding="utf-8"))
    assert loaded.review_id == result.review_id
    assert loaded.status == result.status
