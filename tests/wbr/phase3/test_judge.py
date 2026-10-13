"""TC-3-JUDGE-1：Judge 钩子。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import expert_contract
from wbr.core.harness import GoldenCase, HeuristicJudge, JudgeScore
from wbr.core.orchestration.review import ExpertOutcome, ExpertStatus, ReviewResult


def make_result(with_citations=True, conclusion="推荐 JWT"):
    outcome = ExpertOutcome(
        role_id="expert_a", status=ExpertStatus.COMPLETED,
        raw_text=f'{{"conclusion": "{conclusion}", "confidence": 0.9}}',
        output={"conclusion": conclusion, "confidence": 0.9,
                **({"citations": ["[^1]"]} if with_citations else {})},
    )
    return ReviewResult(
        question="q", expert_outcomes=[outcome],
        final_answer=f"最终结论：{conclusion}",
    )


def test_heuristic_judge_scoring():
    judge = HeuristicJudge()
    case = GoldenCase(case_id="c1", question="q", expected_keywords=["JWT"])
    full = judge.judge(case, make_result(with_citations=True))
    assert full.score == 1.0
    assert full.judge_id == "heuristic"

    no_cite = judge.judge(case, make_result(with_citations=False))
    assert 0.99 >= no_cite.score > full.score - 0.5  # 缺证据扣分
    assert "evidence=0.00" in no_cite.rationale

    miss = judge.judge(case, make_result(conclusion="采用 Session"))
    assert miss.score < no_cite.score  # 关键词全未命中


def test_judge_hook_plugged_into_engine():
    from tests.wbr.factories import coordinator_contract, verifier_contract
    from wbr.core.harness import CaseSuite, RegressionEngine
    from wbr.core.orchestration import ScriptedInvoker

    class StrictJudge:
        def judge(self, case, result) -> JudgeScore:
            return JudgeScore(score=0.2, rationale="always low", judge_id="strict")

    contracts = {
        "coordinator": coordinator_contract(),
        "expert_a": expert_contract("expert_a"),
        "verifier": verifier_contract(),
    }
    scripts = {
        "coordinator": {"assignments": [{"expert_role_id": "expert_a", "sub_question": "q"}]},
        "expert_a": {"conclusion": "c", "confidence": 0.9},
        "verifier": {"passed": True, "scores": {}, "comments": "ok"},
    }
    engine = RegressionEngine(contracts=contracts, invoker=ScriptedInvoker(scripts))
    suite = CaseSuite(suite_id="s")
    suite.add(GoldenCase(case_id="c1", question="q"))
    report = engine.run_suite(suite, judge=StrictJudge(), judge_pass_threshold=0.6)
    cr = report.case_results[0]
    assert cr.judge_score == 0.2
    assert cr.passed is False  # 低分判失败
    assert any("AI Judge" in f for f in cr.failures)

    # 高分 Judge 不影响通过
    class GenerousJudge(StrictJudge):
        def judge(self, case, result) -> JudgeScore:
            return JudgeScore(score=0.95, rationale="generous", judge_id="gen")

    report2 = engine.run_suite(suite, judge=GenerousJudge())
    assert report2.case_results[0].passed is True


def test_heuristic_judge_edge_cases():
    judge = HeuristicJudge(keyword_weight=2.0, schema_weight=1.0, evidence_weight=1.0,
                           judge_id="custom")
    # 无关键词 → 满分关键词分量
    case_no_kw = GoldenCase(case_id="nk", question="q")
    from tests.wbr.factories import expert_contract
    empty = judge.judge(case_no_kw, ReviewResult(question="q", expert_outcomes=[],
                                                 final_answer="没有专家输出"))
    assert empty.score < 1.0  # 证据分与 schema 分为 0
    assert empty.judge_id == "custom"

    # 权重归一化：关键词占比 50%
    case_kw = GoldenCase(case_id="wk", question="q", expected_keywords=["命中"])
    out = ExpertOutcome(role_id="e", status=ExpertStatus.COMPLETED, raw_text="包含命中",
                        output={"conclusion": "命中", "confidence": 1.0})
    r = ReviewResult(question="q", expert_outcomes=[out], final_answer="包含命中")
    s = judge.judge(case_kw, r)
    assert s.score == pytest.approx(0.5 + 0.25 + 0.5 * 0.0 + 0.25 * 0.0 + 0, abs=0.3)


def test_case_result_defaults():
    from wbr.core.harness.engine import CaseResult

    cr = CaseResult(case_id="x")
    assert cr.passed is False and cr.stability_conclusion is None
    assert cr.per_expert == {} and cr.failures == []
