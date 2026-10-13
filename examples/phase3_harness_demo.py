"""阶段3 验收示例：Harness 回归 + 能力退化检测 + 契约缓存 + 审计包导出。

运行：.venv/bin/python examples/phase3_harness_demo.py

场景：修改专家契约（模拟能力退化）后，一键回归全量用例，
自动对比新旧指标并报告退化项；缓存随契约变更自动失效。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from wbr.core.audit.pack import AuditPackBuilder
from wbr.core.audit.trail import AuditTrail
from wbr.core.cache import ContractBoundCache
from wbr.core.harness import (
    BaselineSnapshot,
    CaseSuite,
    GoldenCase,
    RegressionEngine,
)
from wbr.core.orchestration import ScriptedInvoker
from tests_helpers import build_team, make_scripts


def main() -> int:
    trail = AuditTrail()
    team = build_team()  # {coordinator, expert_a, verifier}
    suite = CaseSuite(suite_id="login-suite", version="1.0.0")
    suite.add(GoldenCase(case_id="auth_select", question="登录认证如何选型？",
                         expected_keywords=["JWT"], expert_role_ids=["expert_a"]))
    suite.add(GoldenCase(case_id="evidence_check", question="给出带证据的结论",
                         expert_role_ids=["expert_a"]))
    suite.add(GoldenCase(case_id="disagreement_case", question="有争议的方案",
                         expert_role_ids=["expert_a"], expect_disagreement=True))

    baseline = BaselineSnapshot.capture(contracts=team, suite=suite,
                                        model_fingerprint="scripted-v1")
    print(f"[1] 基线快照 OK  baseline={baseline.baseline_id[:8]}… 契约锁定={len(baseline.contract_hashes)} 项")

    # ---- 第一次回归：专家状态良好 ----
    engine = RegressionEngine(contracts=team, invoker=ScriptedInvoker(make_scripts(degraded=False)),
                              audit=trail)
    report_good = engine.run_suite(suite, baseline=baseline, stability_runs=2)
    m = report_good.metrics
    print(f"[2] 回归#1 OK  通过率={m.overall_pass_rate}  合规率={m.contract_compliance_rate}  "
          f"分歧检出率={m.disagreement_detection_rate}  稳定性={m.expert_conclusion_stability}")

    # ---- 专家"能力退化"（契约降级标记 + 脚本输出劣化）----
    degraded_team = dict(team)
    degraded_team["expert_a"] = team["expert_a"].with_changes(
        **{"identity.description": "DEGRADED"}, bump="minor", changelog="模拟专家能力退化"
    )
    assert baseline.is_current(degraded_team, suite).ok is False
    print("[3] 基线一致性校验：检出契约漂移 ✱")

    engine2 = RegressionEngine(contracts=degraded_team,
                               invoker=ScriptedInvoker(make_scripts(degraded=True)), audit=trail)
    report_bad = engine2.run_suite(suite, baseline=baseline)
    comparison = report_bad.compare_with(report_good)
    print(f"[4] 回归#2 OK  通过率={report_bad.metrics.overall_pass_rate}  "
          f"合规率={report_bad.metrics.contract_compliance_rate}")
    print("    指标变化:", json.dumps(comparison["metrics_delta"], ensure_ascii=False))
    if not comparison["degradations"]:
        print("    [!] 未检出退化（预期应检出）")
        return 1
    for d in comparison["degradations"]:
        print(f"    退化项: {d['metric']}  {d['previous']} → {d['current']} (Δ{d['delta']})")

    # ---- 契约绑定缓存：变更自动失效 ----
    cache = ContractBoundCache()
    expert_v1 = team["expert_a"]
    cache.put(expert_v1, "登录认证如何选型？", None, {"answer": "cached-v1"})
    hit1 = cache.get(expert_v1, "登录认证如何选型？")
    hit2 = cache.get(degraded_team["expert_a"], "登录认证如何选型？")  # 新契约 → 不可命中旧条目
    removed = cache.invalidate_contract(expert_v1)
    print(f"[5] 缓存治理 OK  v1命中={hit1}  v2脏命中={hit2}（应为None）  主动失效={removed} 条")

    # ---- 审计包导出 ----
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "audit-pack.json"
        pack = AuditPackBuilder(trail).build(results=None)
        pack.save(str(p))
        loaded = json.loads(p.read_text(encoding="utf-8"))
        print(f"[6] 审计包导出 OK  events={loaded['integrity']['event_count']}  "
              f"digest={loaded['integrity']['content_digest'][:12]}…  size={p.stat().st_size}B")

    print("\n阶段3 Demo 全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
