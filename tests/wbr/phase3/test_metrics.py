"""TC-3-MET-1~3：指标计算、退化检测、一键回归对比。"""
from __future__ import annotations

import pytest

from wbr.core.harness.metrics import HarnessMetrics, detect_degradation, from_case_results
from wbr.core.orchestration.review import ExpertStatus, ViolationKind


def make_cr(case_id="c1", *, passed=True, experts=None, stability=None,
            expect_disagreement=False, disagreement_detected=False):
    from wbr.core.harness.engine import CaseResult

    cr = CaseResult(case_id=case_id, passed=passed, stability_conclusion=stability,
                    expect_disagreement=expect_disagreement, disagreement_detected=disagreement_detected)
    for role_id, spec in (experts or {}).items():
        cr.per_expert[role_id] = spec
    return cr


OK = {"status": ExpertStatus.COMPLETED.value, "violations": [], "output": {"conclusion": "x"}}
BAD_SCHEMA = {"status": ExpertStatus.FAILED.value, "output": None,
              "violations": [{"kind": ViolationKind.SCHEMA.value, "detail": "缺字段", "path": ""}]}
FORBIDDEN_HIT = {"status": ExpertStatus.FAILED.value, "output": {"conclusion": "x"},
                 "violations": [{"kind": ViolationKind.FORBIDDEN.value, "detail": "命中", "path": ""}]}
EVIDENCE_MISS = {"status": ExpertStatus.FAILED.value, "output": {},
                 "violations": [{"kind": ViolationKind.EVIDENCE.value, "detail": "证据不足", "path": ""}]}


def test_six_metrics_known_values():
    cases = [
        make_cr("c1", experts={  # 2 执行: 1 全合规, 1 schema 违规
            "e1": dict(OK), "e2": dict(BAD_SCHEMA),
        }, passed=True),
        make_cr("c2", experts={  # 2 执行: 1 禁区命中, 1 证据缺失(要求证据)
            "e1": dict(FORBIDDEN_HIT), "e2": dict(EVIDENCE_MISS, evidence_required=True),
        }, passed=False),
    ]
    m = from_case_results(cases)
    assert m.sample_sizes["expert_executions"] == 4
    assert m.contract_compliance_rate == pytest.approx(1 / 4)       # 仅 e1@c1 合规
    assert m.schema_pass_rate == pytest.approx(3 / 4)               # 除 BAD_SCHEMA 外通过
    assert m.forbidden_violation_rate == pytest.approx(1 / 4)
    assert m.evidence_completeness_rate == 0.0                      # 要求证据的 1 项未达标
    assert m.overall_pass_rate == pytest.approx(1 / 2)
    assert m.expert_conclusion_stability is None                    # 未测稳定性
    assert m.disagreement_detection_rate is None                    # 无分歧用例


def test_stability_and_disagreement_rates():
    cases = [
        make_cr("c1", stability=True, expect_disagreement=True, disagreement_detected=True),
        make_cr("c2", stability=False, expect_disagreement=True, disagreement_detected=False),
        make_cr("c3", stability=True, expect_disagreement=False),
    ]
    m = from_case_results(cases, stability_runs=2)
    assert m.expert_conclusion_stability == pytest.approx(2 / 3)
    assert m.disagreement_detection_rate == pytest.approx(1 / 2)


def test_empty_and_none_cases():
    m = from_case_results([])
    assert m.contract_compliance_rate is None
    assert m.overall_pass_rate is None


def test_detect_degradation():
    prev = HarnessMetrics(
        contract_compliance_rate=0.9, schema_pass_rate=0.95,
        forbidden_violation_rate=0.05, expert_conclusion_stability=0.9,
        overall_pass_rate=0.9,
    )
    # 契约合规率下滑 0.1（超过 -0.05 阈值）、禁区违规率上升 0.1（=负向）
    cur = HarnessMetrics(
        contract_compliance_rate=0.8, schema_pass_rate=0.95,
        forbidden_violation_rate=0.15, expert_conclusion_stability=0.9,
        overall_pass_rate=0.9,
    )
    deg = detect_degradation(prev, cur, threshold=-0.05)
    metrics_flagged = {d["metric"] for d in deg}
    assert "contract_compliance_rate" in metrics_flagged
    assert "forbidden_violation_rate" in metrics_flagged  # 上升=退化
    assert "schema_pass_rate" not in metrics_flagged
    assert deg[0]["previous"] is not None


def test_delta_directions():
    a = HarnessMetrics(overall_pass_rate=0.5)
    b = HarnessMetrics(overall_pass_rate=0.75)
    assert b.delta(a)["overall_pass_rate"] == pytest.approx(0.25)
