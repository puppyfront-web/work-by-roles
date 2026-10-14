"""TC-V1.1-FB：反馈闭环。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import coordinator_contract, expert_contract, verifier_contract
from wbr.core.audit.models import AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.harness import CaseSuite, RegressionEngine
from wbr.core.harness.feedback import FeedbackLoop
from wbr.core.orchestration import ScriptedInvoker


def test_record_and_stats():
    loop = FeedbackLoop()
    loop.record(review_id="r1", trace_id="t1", rating="up", question="q1")
    loop.record(review_id="r2", trace_id="t2", rating="down", question="q2", categories=["证据不足"])
    loop.record(review_id="r3", trace_id="t3", rating="down", question="q2")
    s = loop.stats()
    assert (s["total"], s["up"], s["down"]) == (3, 1, 2)
    assert s["down_rate"] == pytest.approx(2 / 3)
    assert s["by_category"] == {"证据不足": 1}


def test_invalid_rating_rejected():
    loop = FeedbackLoop()
    with pytest.raises(ValueError, match="rating"):
        loop.record(review_id="r", trace_id="t", rating="meh", question="q")


def test_down_feedback_aggregates_to_golden_cases():
    loop = FeedbackLoop()
    for i in range(3):
        loop.record(review_id=f"r{i}", trace_id=f"t{i}", rating="down",
                    question="缓存穿透如何防？", categories=["答案质量"])
    loop.record(review_id="rx", trace_id="tx", rating="down", question="偶发的坏问题")  # 仅1条
    suite = loop.to_golden_cases(min_samples=3, suite_id="fb-suite")
    ids = [c.case_id for c in suite.cases]
    assert len(ids) == 1
    case = suite.cases[0]
    assert case.question == "缓存穿透如何防？"
    assert "答案质量" in case.tags and case.notes  # 携带类别与反馈注释


def test_golden_case_feeds_regression_engine():
    """闭环终点：反馈用例可被回归引擎直接执行。"""
    loop = FeedbackLoop()
    loop.record(review_id="r", trace_id="t", rating="down", question="登录认证怎么选型？")
    suite = loop.to_golden_cases(min_samples=1, suite_id="fb")

    contracts = {
        "coordinator": coordinator_contract(),
        "expert_a": expert_contract("expert_a"),
        "verifier": verifier_contract(),
    }
    scripts = {
        "coordinator": {"assignments": [{"expert_role_id": "expert_a", "sub_question": "q"}]},
        "expert_a": {"conclusion": "推荐 JWT", "confidence": 0.9},
        "verifier": {"passed": True, "scores": {"completeness": 0.8, "accuracy": 0.8},
                     "comments": "ok", "final_answer": "推荐 JWT"},
    }
    engine = RegressionEngine(contracts=contracts, invoker=ScriptedInvoker(scripts))
    report = engine.run_suite(suite)
    assert report.metrics.overall_pass_rate == 1.0


def test_pending_questions_and_clear():
    loop = FeedbackLoop()
    loop.record(review_id="r", trace_id="t", rating="down", question="问题A")
    assert loop.pending_questions() == ["问题A"]
    suite = loop.to_golden_cases(min_samples=1)
    assert loop.pending_questions() == []  # 已聚合的不再 pending


def test_audit_events_recorded():
    trail = AuditTrail()
    loop = FeedbackLoop(audit=trail)
    loop.record(review_id="r", trace_id="t1", rating="down", question="q")
    types = {e.event_type for e in trail.events}
    assert AuditEventType.MEMORY_ACCESS in types  # 复用审计通道（kb_event 标记）
    assert any(e.payload.get("fb_event") == "feedback" for e in trail.events)
