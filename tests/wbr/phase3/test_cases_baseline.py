"""TC-3-CASE-1 / TC-3-BASE-1：用例库与基线快照。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import coordinator_contract, expert_contract, verifier_contract
from wbr.core.exceptions import HarnessError
from wbr.core.harness import BaselineSnapshot, CaseSuite, GoldenCase


def make_suite() -> CaseSuite:
    suite = CaseSuite(suite_id="s-1")
    suite.add(GoldenCase(case_id="c1", question="如何设计登录？", expected_keywords=["JWT"],
                         expert_role_ids=["expert_a"]))
    suite.add(GoldenCase(case_id="c2", question="如何设计缓存？", tags=["perf"]))
    return suite


def test_suite_persistence_roundtrip(tmp_path):
    suite = make_suite()
    p = tmp_path / "suite.json"
    suite.save(str(p))
    loaded = CaseSuite.load(str(p))
    assert loaded.suite_id == suite.suite_id
    assert [c.case_id for c in loaded.cases] == ["c1", "c2"]


def test_duplicate_case_id_rejected():
    suite = CaseSuite(suite_id="s")
    suite.add(GoldenCase(case_id="dup", question="q1"))
    with pytest.raises(HarnessError, match="已存在"):
        suite.add(GoldenCase(case_id="dup", question="q2"))
    with pytest.raises(HarnessError, match="唯一"):
        CaseSuite(cases=[GoldenCase(case_id="x", question="1"), GoldenCase(case_id="x", question="2")])


def test_content_hash_sensitive():
    suite = make_suite()
    h1 = suite.content_hash()
    suite.add(GoldenCase(case_id="c3", question="q3"))
    assert suite.content_hash() != h1


def test_baseline_capture_and_consistency():
    contracts = {
        "coordinator": coordinator_contract(),
        "expert_a": expert_contract("expert_a"),
        "verifier": verifier_contract(),
    }
    suite = make_suite()
    snap = BaselineSnapshot.capture(contracts=contracts, suite=suite, model_fingerprint="gpt-x@2026-01")
    assert snap.model_fingerprint == "gpt-x@2026-01"
    assert snap.is_current(contracts, suite).ok is True

    # 契约变更 → 不一致报告
    changed = dict(contracts)
    changed["expert_a"] = expert_contract("expert_a").with_changes(**{"identity.description": "v2"})
    report = snap.is_current(changed, suite)
    assert report.ok is False
    assert report.contract_mismatches and "expert_a" in report.contract_mismatches[0]

    # 角色缺失 → missing_roles
    report2 = snap.is_current({"coordinator": contracts["coordinator"]}, suite)
    assert "expert_a" in report2.missing_roles

    # 用例库变更 → suite_matches False
    suite2 = make_suite()
    suite2.add(GoldenCase(case_id="c9", question="q9"))
    report3 = snap.is_current(contracts, suite2)
    assert report3.suite_matches is False and report3.ok is False


def test_baseline_persistence(tmp_path):
    snap = BaselineSnapshot.capture(
        contracts={"e": expert_contract("expert_a")}, suite=make_suite()
    )
    p = tmp_path / "baseline.json"
    snap.save(str(p))
    loaded = BaselineSnapshot.load(str(p))
    assert loaded.contract_hashes == snap.contract_hashes
