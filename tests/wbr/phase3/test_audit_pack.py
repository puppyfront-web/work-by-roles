"""TC-3-PACK-1~2：标准化审计包导出。"""
from __future__ import annotations

import json

from tests.wbr.factories import (
    coordinator_contract,
    expert_contract,
    verifier_contract,
)
from wbr.core.audit.pack import AuditPack, AuditPackBuilder
from wbr.core.audit.trail import AuditTrail
from wbr.core.harness import RegressionEngine
from wbr.core.orchestration import ScriptedInvoker


def build_session_artifacts():
    scripts = {
        "coordinator": {"assignments": [{"expert_role_id": "expert_a", "sub_question": "选型"}]},
        "expert_a": {"conclusion": "推荐 JWT", "confidence": 0.9, "citations": ["[^1]"]},
        "verifier": {"passed": True, "scores": {"completeness": 0.8, "accuracy": 0.8},
                     "comments": "ok", "final_answer": "推荐 JWT"},
    }
    trail = AuditTrail()
    engine = RegressionEngine(
        contracts={
            "coordinator": coordinator_contract(),
            "expert_a": expert_contract("expert_a"),
            "verifier": verifier_contract(),
        },
        invoker=ScriptedInvoker(scripts),
        audit=trail,
    )
    from wbr.core.harness import CaseSuite, GoldenCase

    suite = CaseSuite(suite_id="s")
    suite.add(GoldenCase(case_id="c1", question="认证设计？", expert_role_ids=["expert_a"]))
    report = engine.run_suite(suite)
    return trail, report.case_results[0].review_id, report.case_results[0].trace_id


def test_pack_structure_complete():
    trail, review_id, trace_id = build_session_artifacts()
    from wbr.core.harness.engine import RegressionReport  # 取回 result 重建

    # 通过 trail + 单独重放拿 ReviewResult 不方便，这里直接构造查询
    pack = AuditPackBuilder(trail).build(trace_ids=[trace_id])
    assert pack.format_version == "1.0"
    assert pack.generator["name"] == "wbr"
    assert pack.integrity["event_count"] == len(pack.events)
    assert pack.integrity["sessions_count"] == 0  # 未提供 results
    assert pack.integrity["content_digest"]
    json.dumps(pack.to_json(), ensure_ascii=False)  # 可序列化


def test_pack_digest_stable_and_sensitive():
    trail, _, trace_id = build_session_artifacts()
    p1 = AuditPackBuilder(trail).build(trace_ids=[trace_id])
    p2 = AuditPackBuilder(trail).build(trace_ids=[trace_id])
    assert p1.integrity["content_digest"] == p2.integrity["content_digest"]
    # 内容变化 → digest 变化
    from wbr.core.audit.models import AuditEvent, AuditEventType

    trail.append(AuditEvent(event_type=AuditEventType.TOKEN_RECORD, trace_id=trace_id,
                            payload={"tokens": 999}))
    p3 = AuditPackBuilder(trail).build(trace_ids=[trace_id])
    assert p3.integrity["content_digest"] != p1.integrity["content_digest"]


def test_pack_sessions_with_and_without_contents():
    scripts = {
        "coordinator": {"assignments": [{"expert_role_id": "expert_a", "sub_question": "选型"}]},
        "expert_a": {"conclusion": "推荐 JWT", "confidence": 0.9, "citations": ["[^1]"]},
        "verifier": {"passed": True, "scores": {"completeness": 0.8, "accuracy": 0.8},
                     "comments": "ok", "final_answer": "推荐 JWT"},
    }
    trail = AuditTrail()
    engine = RegressionEngine(
        contracts={
            "coordinator": coordinator_contract(),
            "expert_a": expert_contract("expert_a"),
            "verifier": verifier_contract(),
        },
        invoker=ScriptedInvoker(scripts),
        audit=trail,
    )
    from wbr.core.harness import CaseSuite, GoldenCase

    suite = CaseSuite(suite_id="s")
    suite.add(GoldenCase(case_id="c1", question="认证设计？", expert_role_ids=["expert_a"]))
    report = engine.run_suite(suite)
    result = report.case_results[0]
    from wbr.core.orchestration.review import ReviewResult as RR

    # 从 trail 无法直接取 result，重建轻量 result 用于会话摘要
    session_result = RR(question="认证设计？", trace_id=result.trace_id,
                        coordinator_plan={"assignments": []})

    redacted = AuditPackBuilder(trail).build(trace_ids=[result.trace_id],
                                             results=[session_result])
    packed = redacted.sessions[0]
    assert packed.expert_summaries == []  # result 无 outcomes（轻量构造）→ 不泄露
    assert redacted.integrity["include_contents"] is False

    # 完整 result：脱敏模式含 digest 不含全文
    full_result = _rebuild_full_result(scripts)
    full = AuditPackBuilder(trail).build(results=[full_result])
    s = full.sessions[0]
    assert s.expert_summaries and "output_digest" in s.expert_summaries[0]
    assert "output" not in s.expert_summaries[0]

    opened = AuditPackBuilder(trail, include_contents=True).build(results=[full_result])
    s2 = opened.sessions[0]
    assert s2.expert_summaries[0]["output"]["conclusion"] == "推荐 JWT"
    assert s2.coordinator_plan  # contents 模式包含 plan


def _rebuild_full_result(scripts):
    """跑一次会审拿完整 ReviewResult（附带审计事件）。"""
    from wbr.core.orchestration import ReviewSession

    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a")],
        verifier_contract=verifier_contract(),
        invoker=ScriptedInvoker(scripts),
        audit=trail_holder["trail"],
    )
    return session.run("认证设计？")


trail_holder = {"trail": AuditTrail()}


def test_pack_save_load(tmp_path):
    trail, _, trace_id = build_session_artifacts()
    pack = AuditPackBuilder(trail).build(trace_ids=[trace_id])
    p = tmp_path / "pack.json"
    pack.save(str(p))
    loaded = AuditPack.load(str(p))
    assert loaded.integrity["content_digest"] == pack.integrity["content_digest"]
