"""TC-3-ENG-1 / TC-3-REG-1：回归引擎与一键回归全链路。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import (
    coordinator_contract,
    expert_contract,
    verifier_contract,
)
from wbr.core.exceptions import HarnessError
from wbr.core.harness import (
    BaselineSnapshot,
    CaseSuite,
    GoldenCase,
    HeuristicJudge,
    RegressionEngine,
)
from wbr.core.orchestration import ScriptedInvoker


def make_contracts():
    return {
        "coordinator": coordinator_contract(),
        "expert_a": expert_contract("expert_a"),
        "verifier": verifier_contract(),
    }


def make_scripts(conclusion="采用 JWT", confidence=0.9):
    return {
        "coordinator": {"assignments": [{"expert_role_id": "expert_a", "sub_question": "认证选型"}]},
        "expert_a": {"conclusion": conclusion, "confidence": confidence, "citations": ["[^1] 方案文档"]},
        "verifier": {"passed": True, "scores": {"completeness": 0.9, "accuracy": 0.85},
                     "comments": "结论有据", "final_answer": f"最终结论：{conclusion}"},
    }


def make_suite(**case_kw) -> CaseSuite:
    suite = CaseSuite(suite_id="reg-suite")
    suite.add(GoldenCase(
        case_id="auth", question="登录认证怎么设计？",
        expected_keywords=["JWT"], expert_role_ids=["expert_a"],
        **case_kw,
    ))
    return suite


def test_run_suite_produces_report_and_pass():
    engine = RegressionEngine(contracts=make_contracts(), invoker=ScriptedInvoker(make_scripts()))
    report = engine.run_suite(make_suite(), stability_runs=2)
    cr = report.case_results[0]
    assert cr.case_id == "auth"
    assert cr.passed is True
    assert cr.verdict_passed is True
    assert cr.stability_conclusion is True  # 两次运行结论一致
    assert report.metrics.overall_pass_rate == 1.0
    assert report.metrics.contract_compliance_rate == 1.0
    assert report.metrics.expert_conclusion_stability == 1.0
    assert report.finished_at >= report.started_at
    assert report.suite_id == "reg-suite"


def test_keyword_failure_fails_case():
    engine = RegressionEngine(contracts=make_contracts(), invoker=ScriptedInvoker(make_scripts()))
    suite = CaseSuite(suite_id="s")
    suite.add(GoldenCase(case_id="need_kerberos", question="q", expected_keywords=["Kerberos"]))
    report = engine.run_suite(suite)
    cr = report.case_results[0]
    assert cr.passed is False
    assert any("Kerberos" in f for f in cr.failures)


def test_expected_schema_violation_recorded():
    engine = RegressionEngine(contracts=make_contracts(), invoker=ScriptedInvoker(make_scripts()))
    suite = CaseSuite(suite_id="s")
    suite.add(GoldenCase(
        case_id="strict_case", question="q",
        expected_schema={"type": "object", "required": ["conclusion", "confidence", "extra"]},
        expert_role_ids=["expert_a"],
    ))
    report = engine.run_suite(suite)
    cr = report.case_results[0]
    assert cr.passed is False
    assert any("extra" in f for f in cr.failures)


def test_rerun_after_contract_change_one_click_regression():
    """★ 修改契约后一键回归：新旧报告对比 + 基线一致性联动。"""
    contracts = make_contracts()
    suite = make_suite()
    baseline = BaselineSnapshot.capture(contracts=contracts, suite=suite)
    engine = RegressionEngine(contracts=contracts, invoker=ScriptedInvoker(make_scripts()))
    first = engine.run_suite(suite, baseline=baseline)
    assert first.metrics.overall_pass_rate == 1.0

    # 修改契约：专家禁止提及 "JWT"（会被输出里的 final_answer 命中吗？verifier 输出包含 JWT → 不改 verifier）
    contracts_changed = dict(contracts)
    contracts_changed["expert_a"] = contracts["expert_a"].with_changes(
        **{"identity.description": "收紧后的描述"}, bump="minor", changelog="收紧输出约束"
    )
    assert baseline.is_current(contracts_changed, suite).ok is False  # 基线检出契约漂移

    engine2 = RegressionEngine(contracts=contracts_changed, invoker=ScriptedInvoker(make_scripts()))
    second = engine2.run_suite(suite, baseline=baseline)
    comparison = second.compare_with(first)
    assert "metrics_delta" in comparison and "degradations" in comparison
    assert second.baseline_id == baseline.baseline_id


def test_engine_requires_roles():
    contracts = make_contracts()
    del contracts["verifier"]
    with pytest.raises(HarnessError, match="verifier"):
        RegressionEngine(contracts=contracts, invoker=ScriptedInvoker(make_scripts()))
    with pytest.raises(HarnessError, match="不能为空"):
        RegressionEngine(contracts={}, invoker=ScriptedInvoker(make_scripts()))


def test_empty_suite_rejected():
    engine = RegressionEngine(contracts=make_contracts(), invoker=ScriptedInvoker(make_scripts()))
    with pytest.raises(HarnessError, match="为空"):
        engine.run_suite(CaseSuite(suite_id="empty"))


def test_expert_contract_missing_for_case():
    engine = RegressionEngine(contracts=make_contracts(), invoker=ScriptedInvoker(make_scripts()))
    suite = CaseSuite(suite_id="s")
    suite.add(GoldenCase(case_id="ghost", question="q", expert_role_ids=["no_such_expert"]))
    with pytest.raises(HarnessError, match="不存在"):
        engine.run_suite(suite)


def test_report_persistence(tmp_path):
    engine = RegressionEngine(contracts=make_contracts(), invoker=ScriptedInvoker(make_scripts()))
    report = engine.run_suite(make_suite())
    p = tmp_path / "report.json"
    report.save(str(p))
    from wbr.core.harness.engine import RegressionReport

    loaded = RegressionReport.model_validate_json(p.read_text(encoding="utf-8"))
    assert loaded.metrics.overall_pass_rate == report.metrics.overall_pass_rate
