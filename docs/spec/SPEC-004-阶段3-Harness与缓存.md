# SPEC-004 · 阶段3 · V0.3 Harness 评估体系与契约缓存

> 前置：阶段2 完成。目标版本：0.3.0。本阶段为核心壁垒：可回归、可度量、缓存不脏。

## 1. Harness 内核 `wbr/core/harness/`

### 1.1 黄金用例库 `cases.py`
```python
GoldenCase: case_id / question / expected_keywords: list[str] / expected_schema: dict|None
          / context: dict / expert_role_ids: list[str] / tags: list[str] / notes
CaseSuite: suite_id / cases: list[GoldenCase]（case_id 唯一）/ version
          save/load(path)（JSON）
```

### 1.2 任务基线快照 `baseline.py`
```python
BaselineSnapshot: baseline_id / created_at
  contract_hashes: dict[role_id, sha]        # 锁定契约版本
  suite_hash: sha                             # 锁定用例库版本
  model_fingerprint: str                      # 模型标识/版本（由 invoker 提供）
  invoker_fingerprint() 协议方法注入
save/load；snapshot 与当前契约集合的一致性校验 `is_current(contracts, suite) -> ConsistencyReport`
```

### 1.3 批量回归引擎 `engine.py`
```python
RegressionEngine(*, invoker_factory: Callable[[RoleContract], ModelInvoker] | invoker,
                 contracts: dict[role_id, RoleContract], memory_factory=None)
run_suite(suite, *, baseline: BaselineSnapshot|None) -> RegressionReport
```
- 每个用例执行一次完整会审（复用 Core ReviewSession）；收集每专家输出 + 校验结果（schema/禁区/证据）。
- `RegressionReport`: report_id / suite_id / baseline_id? / case_results: list[CaseResult] / metrics: HarnessMetrics / started_at/finished_at；`to_json()/save(path)`。
- `CaseResult`: case_id / review_id / trace_id / per_expert: dict[role_id, ExpertOutcome] / verdict / passed(bool) / failures: list。

### 1.4 核心指标 `metrics.py`（自动统计，全部 0~1，None=分母为0）
```python
HarnessMetrics:
  contract_compliance_rate      # 无任何违规结局的专家执行 / 总专家执行
  schema_pass_rate              # schema 校验通过 / 总校验
  forbidden_violation_rate      # 禁区命中 / 总校验（越低越好）
  evidence_completeness_rate    # 满足 evidence_spec 的输出 / 要求证据的输出
  expert_conclusion_stability   # 同 case 重复运行(≥2 次)结论一致的比例（stability_runs 参数）
  disagreement_detection_rate   # 构造含分歧用例中被正确检出分歧的比例
  overall_pass_rate             # 通过用例 / 总用例
from_case_results(case_results, *, stability_runs=1) -> HarnessMetrics（静态工厂）
degradation(previous, current) -> dict[metric, delta]   # 退化检测：显著负向变化列出
```
- **能力退化检测**：`detect_degradation(prev_report, cur_report, threshold=-0.05)` 返回退化指标清单；供"修改契约后一键回归"场景使用。

### 1.5 AI Judge 钩子 `judge.py`
```python
JudgeHook(Protocol): judge(case: GoldenCase, result: ReviewResult) -> JudgeScore
JudgeScore: score: float(0,1) / rationale: str / judge_id: str
HeuristicJudge(JudgeHook): 基础实现——expected_keywords 命中率 + schema 通过 + 证据引用计数的加权规则分
RegressionEngine(judge=...) 挂钩：judge 分数并入 CaseResult.judge_score，参与 passed 判定（提供时）
```

## 2. 契约绑定语义缓存 `wbr/core/cache/`

### 2.1 Key 规则（锁定）
`cache_key = sha256(f"{contract_hash}|{question_hash}|{evidence_snapshot_id}")`
- `question_hash = sha256(canonical_json(normalize(question)))`，normalize=去首尾空白+全角半角归一。
- `evidence_snapshot_id`：无证据时取 `"none"`；有证据时为其 canonical JSON 的 sha。

### 2.2 `ContractBoundCache`
```python
__init__(backend: CacheBackend|None=None, *, enabled=True, max_entries=4096, audit=None)
get(contract: RoleContract, question, evidence) -> CacheHit|None
put(contract, question, evidence, value: dict) -> None
stats() -> CacheStats(hits, misses, hit_rate, invalidations, evictions)
invalidate_contract(contract_hash|contract)   # 契约变更自动失效
```
- 失效机制：缓存条目记录 `contract_hash`；`put/get` 前校验条目 hash 与当前契约 hash 一致，不一致即丢弃并计 invalidation（双保险：主动 invalidate + 被动校验）。
- 驱逐：超 max_entries 时 LRU；`enabled=False` 时全直通（统计 miss）。
- `CacheBackend` 协议（get/set/delete/keys/clear）+ `InMemoryCacheBackend`；Redis 后端由 adapters/storage 复用 StorageBackend 桥接（阶段3 提供 `RedisCacheBackend`）。

## 3. 标准化审计包导出 `wbr/core/audit/pack.py`
```python
AuditPackBuilder(trail, *, include_contents=False)
build(trace_ids|review_ids) -> AuditPack
AuditPack.to_json() / save(path)
结构: {
  "format_version": "1.0", "exported_at", "generator": {"name":"wbr","version"},
  "sessions": [ {review 元数据, coordinator plan, expert outcomes(含 violations), verdict,
                 disagreements, token usage, cache_stats?} ],
  "events": [全量审计事件(按 trace 聚合)], "integrity": {"event_count", "sessions_count", "content_digest"}
}
```
- `include_contents=False` 时专家全文以摘要替代（默认脱敏导出）；digest = 全事件 canonical JSON sha256。

## 4. 非目标
高级语义缓存（向量匹配）、AI Judge 的 LLM 实现（仅钩子+启发式基实现）、审计哈希链防篡改（V2.0）、知识库锁定字段仅存指纹。

## 5. 验收标准 → 测试映射（tests/wbr/phase3/）

| 验收标准 | 测试 |
|---|---|
| 修改契约后一键回归全量用例并给出新旧对比 | `test_regression_flow.py::test_rerun_after_contract_change` |
| 能力退化自动检测 | `test_metrics.py::test_detect_degradation` |
| 指标计算正确（构造已知结果断言各率值） | `test_metrics.py`（参数化） |
| 缓存 Key 三要素、命中/未命中/命中率 | `test_contract_cache.py` |
| 契约变更自动失效（主动+被动双路径） | `test_contract_cache.py::test_invalidate_on_contract_change` |
| 缓存不脏数据（不同 evidence/问题不串） | `test_contract_cache.py::test_no_cross_pollination` |
| 基线快照锁定与一致性校验 | `test_baseline.py` |
| 审计包导出结构完整、脱敏、digest 稳定 | `test_audit_pack.py` |
| GoldenCase/Suite 持久化往返 | `test_cases.py` |
| Judge 钩子挂钩生效 | `test_judge.py` |
| harness/cache 模块覆盖率 ≥90% | `pytest --cov` 报告 |
