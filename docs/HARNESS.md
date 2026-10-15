# Harness：回归、基线与指标

Harness 是本系统的质量门禁：把"专家团能力"变成可回归、可对比、可报警的资产。

## 核心概念

- **黄金用例库 CaseSuite**：`GoldenCase(question, expected_keywords, expected_schema, expert_role_ids, expect_disagreement)`；case_id 唯一，可 JSON 持久化。
- **基线快照 BaselineSnapshot**：锁定 `{role_id → 契约哈希}` + 用例库哈希 + 模型指纹。`is_current()` 检出契约/用例漂移。
- **回归引擎 RegressionEngine**：逐用例跑完整会审（复用 Core ReviewSession），产出 `RegressionReport`。
- **AI Judge 钩子**：`JudgeHook.judge(case, result) -> JudgeScore`；内置 `HeuristicJudge`（关键词命中率 + Schema 通过 + 证据引用加权）；低分可判用例失败。

## 六项指标（全部 0~1，自动统计）

| 指标 | 含义 | 方向 |
|---|---|---|
| contract_compliance_rate | 无任何违规且完成的专家执行占比 | 越高越好 |
| schema_pass_rate | 输出 Schema 达标占比 | 越高越好 |
| forbidden_violation_rate | 禁区命中占比 | **越低越好**（退化检测自动取反） |
| evidence_completeness_rate | 要求证据的输出中引用达标占比 | 越高越好 |
| expert_conclusion_stability | 同用例重复运行（stability_runs≥2）结论一致占比 | 越高越好 |
| disagreement_detection_rate | 构造的分歧用例中被检出的占比 | 越高越好 |
| overall_pass_rate | 通过用例 / 总用例 | 越高越好 |

## 标准工作流：修改契约 → 一键回归 → 退化告警

```python
baseline = BaselineSnapshot.capture(contracts=contracts, suite=suite, model_fingerprint="gpt-x@2026-01")
report_v1 = RegressionEngine(contracts=contracts, invoker=invoker).run_suite(suite, baseline=baseline)

# ... 修改契约（放宽禁区 / 换模型 / 调提示词）...
contracts["expert_a"] = contracts["expert_a"].with_changes(
    **{"forbidden.behaviors": [...]}, bump="minor", changelog="...")

assert not baseline.is_current(contracts, suite).ok     # 1) 基线检出漂移
report_v2 = RegressionEngine(contracts=contracts, invoker=invoker).run_suite(
    suite, baseline=baseline, stability_runs=2)         # 2) 一键回归全量用例
diff = report_v2.compare_with(report_v1)                # 3) 对比
if diff["degradations"]:
    alert(diff)   # [{metric, previous, current, delta}] —— 能力退化自动检测（阈值默认 -0.05）
```

## 缓存联动

回归与会审共享 `ContractBoundCache`：Key = 契约哈希 ‖ 问题哈希 ‖ 证据快照 ID。
契约变更后旧条目因 Key 失配天然不可命中（被动防线），亦可 `invalidate_contract()` 主动清除；
命中路径 <1ms（基准门禁）。

## 审计交付

每次回归/会审的完整链路可导出标准审计包（`AuditPackBuilder`，JSON、脱敏 + content_digest），
满足"可追溯交付物"要求。

示例：[examples/phase3_harness_demo.py](https://github.com/puppyfront-web/work-by-roles/blob/main/examples/phase3_harness_demo.py)（运行即见退化检出输出）。
