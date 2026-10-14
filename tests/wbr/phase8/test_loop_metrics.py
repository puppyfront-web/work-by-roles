"""TC-V2.1-METRICS：意图/Loop/辩论三组专项指标。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import expert_contract
from wbr.core.harness.loop_metrics import (
    DebateLoopMetrics,
    IntentMetrics,
    LoopMetrics,
)
from wbr.core.loop_config import LoopSummarySnapshot
from wbr.core.orchestration.debate import DebateResult
from wbr.core.orchestration.intent import IntentResult, IntentType, NextAction


def intent_result(t: IntentType, action: NextAction | None = None) -> IntentResult:
    return IntentResult(intent_type=t, confidence=0.9,
                        next_action=action or IntentPipelineDefault(t))


def IntentPipelineDefault(t: IntentType) -> NextAction:
    from wbr.core.orchestration.intent import NextAction as NA

    return {
        IntentType.STANDARD_REVIEW: NA.RUN_DISASSEMBLE,
        IntentType.MISSING_INFO: NA.ASK_USER,
        IntentType.OUT_OF_SCOPE: NA.REJECT,
        IntentType.AMBIGUOUS: NA.ASK_USER,
        IntentType.LIGHTWEIGHT_QUERY: NA.LIGHTWEIGHT_SINGLE_EXPERT,
    }[t]


def test_intent_metrics_with_expected_labels():
    results = [
        intent_result(IntentType.STANDARD_REVIEW),
        intent_result(IntentType.OUT_OF_SCOPE),
        intent_result(IntentType.AMBIGUOUS),
        intent_result(IntentType.STANDARD_REVIEW),  # 误分类（期望 AMBIGUOUS）
    ]
    expected = [IntentType.STANDARD_REVIEW, IntentType.OUT_OF_SCOPE,
                IntentType.AMBIGUOUS, IntentType.AMBIGUOUS]
    m = IntentMetrics.from_results(results, expected)
    assert m.accuracy == pytest.approx(3 / 4)
    assert m.false_reject_rate == 0.0
    assert m.ambiguous_detection_rate == pytest.approx(1 / 2)
    assert m.sample_sizes["total"] == 4


def test_intent_metrics_false_reject_and_empty():
    results = [intent_result(IntentType.STANDARD_REVIEW, NextAction.REJECT)]
    m = IntentMetrics.from_results(results, expected=[IntentType.STANDARD_REVIEW])
    assert m.false_reject_rate == 1.0
    empty = IntentMetrics.from_results([])
    assert empty.accuracy is None


def snap(rounds, stopped, *, escalated=False, tokens=50):
    return LoopSummarySnapshot(role_id="expert_a", sub_question="q", rounds_used=rounds,
                               conclusion="c", stopped_because=stopped,
                               token_used=tokens, escalated_hitl=escalated)


def test_loop_metrics_aggregation():
    snaps = [
        snap(1, "evidence_satisfied"),
        snap(3, "max_rounds_risk"),
        snap(2, "quota_exhausted_hitl", escalated=True, tokens=200),
    ]
    m = LoopMetrics.from_snapshots(snaps, main_task_tokens=1000)
    assert m.avg_rounds == pytest.approx(2.0)
    assert m.timeout_rate == pytest.approx(1 / 3)
    assert m.escalate_rate == pytest.approx(1 / 3)
    assert m.loop_token_ratio == pytest.approx(300 / 1000)
    assert LoopMetrics.from_snapshots([]).avg_rounds is None


def test_debate_metrics():
    r_hitl = DebateResult(topic="t", escalated_to_hitl=True)
    r_conv = DebateResult(topic="t", escalated_to_hitl=False)
    m = DebateLoopMetrics.from_results([r_hitl, r_conv])
    assert m.convergence_rate == 0.5
    assert m.round_limit_exceeded_rate == 0.5
    assert DebateLoopMetrics.from_results([]).convergence_rate is None
