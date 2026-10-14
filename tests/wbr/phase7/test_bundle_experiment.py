"""TC-V2-BUNDLE / TC-V2-EXP：基线 Bundle 与灰度 A/B。"""
from __future__ import annotations

import json

import pytest

from tests.wbr.factories import (
    coordinator_contract,
    expert_contract,
    verifier_contract,
)
from wbr.core.bundle import BaselineBundle
from wbr.core.experiment import ABExperiment, ABVariant
from wbr.core.harness import BaselineSnapshot, CaseSuite, GoldenCase, RegressionEngine
from wbr.core.orchestration import ScriptedInvoker
from wbr.app.store import ContractRegistry


def make_team(description_suffix: str = "") -> dict:
    return {
        "coordinator": coordinator_contract(),
        "expert_a": expert_contract("expert_a").with_changes(
            **{"identity.description": f"变体{description_suffix}"}),
        "verifier": verifier_contract(),
    }


def make_suite() -> CaseSuite:
    suite = CaseSuite(suite_id="ab-suite")
    suite.add(GoldenCase(case_id="c1", question="登录认证怎么设计？", expert_role_ids=["expert_a"]))
    return suite


def make_scripts(final="推荐 JWT"):
    return {
        "coordinator": {"assignments": [{"expert_role_id": "expert_a", "sub_question": "q"}]},
        "expert_a": {"conclusion": final, "confidence": 0.9},
        "verifier": {"passed": True, "scores": {"completeness": 0.8, "accuracy": 0.8},
                     "comments": "ok", "final_answer": final},
    }


# ---------- E4 Bundle ----------
def test_bundle_pack_load_verify(tmp_path):
    contracts = make_team()
    suite = make_suite()
    baseline = BaselineSnapshot.capture(contracts=contracts, suite=suite, model_fingerprint="m1")
    bundle = BaselineBundle.pack(contracts=contracts, suite=suite, baseline=baseline)
    assert bundle.verify().ok is True

    p = tmp_path / "bundle.json"
    bundle.save(str(p))
    loaded = BaselineBundle.load(str(p))
    assert loaded.verify().ok is True
    # 落回注册表
    reg = ContractRegistry(tmp_path / "restored")
    loaded.to_registry(reg)
    assert reg.get("expert_a") is not None
    assert loaded.get_suite().cases[0].case_id == "c1"
    assert loaded.get_baseline().model_fingerprint == "m1"


def test_bundle_tamper_detected_and_located(tmp_path):
    bundle = BaselineBundle.pack(contracts=make_team(), suite=make_suite(),
                                 baseline=BaselineSnapshot.capture(
                                     contracts=make_team(), suite=make_suite()))
    data = json.loads(bundle.to_json())
    # 篡改一个契约字段
    data["contracts"][0]["identity"]["name"] = "被篡改"
    from wbr.core.bundle import BaselineBundle as BB

    tampered = BB.model_validate(data)
    ok = tampered.verify()
    assert ok.ok is False
    assert "contracts" in (ok.broken_file or "")


def test_bundle_json_serializable():
    bundle = BaselineBundle.pack(contracts=make_team(), suite=make_suite(),
                                 baseline=BaselineSnapshot.capture(
                                     contracts=make_team(), suite=make_suite()))
    json.loads(bundle.to_json())


# ---------- E5 A/B ----------
def test_ab_variant_homogeneity_required():
    exp = ABExperiment(experiment_id="exp1", suite=make_suite(),
                       invoker=ScriptedInvoker(make_scripts()))
    exp.add_variant(ABVariant(name="A", contracts=make_team()))
    bad = make_team()
    del bad["verifier"]
    with pytest.raises(Exception, match="同构"):
        exp.add_variant(ABVariant(name="B", contracts=bad))


def test_split_deterministic_and_balanced_enough():
    exp = ABExperiment(experiment_id="exp1", suite=make_suite(),
                       invoker=ScriptedInvoker(make_scripts()))
    exp.add_variant(ABVariant(name="A", contracts=make_team("A")))
    exp.add_variant(ABVariant(name="B", contracts=make_team("B")))
    picks = {exp.split(f"user-{i}") for i in range(100)}
    assert picks <= {"A", "B"}
    assert len(picks) == 2  # 100 用户应覆盖两个变体
    assert exp.split("user-1") == exp.split("user-1")  # 确定性


def test_ab_run_and_winner():
    exp = ABExperiment(experiment_id="exp1", suite=make_suite(),
                       invoker=ScriptedInvoker(make_scripts()))
    exp.add_variant(ABVariant(name="A", contracts=make_team("A")))
    exp.add_variant(ABVariant(name="B", contracts=make_team("B")))
    report = exp.run()
    assert set(report.per_variant) == {"A", "B"}
    assert report.winner in ("A", "B", None)
    assert report.decision_reason
    # 相同脚本下两边全过 → 平局保守不切换
    assert report.winner is None and "并列" in report.decision_reason


def test_ab_winner_prefers_higher_pass_rate():
    exp = ABExperiment(experiment_id="exp2", suite=make_suite(),
                       invoker=ScriptedInvoker(make_scripts()))
    exp.add_variant(ABVariant(name="A", contracts=make_team("A")))
    # B 额外含必然失败用例（期望关键词不满足）→ B pass_rate 更低
    suite_b = make_suite()
    suite_b.add(GoldenCase(case_id="hard", question="q2", expected_keywords=["Kerberos"],
                           expert_role_ids=["expert_a"]))
    exp.add_variant(ABVariant(name="B", contracts=make_team("B")), suite=suite_b)
    report = exp.run()
    assert report.winner == "A"
    assert "overall_pass_rate" in report.decision_reason
