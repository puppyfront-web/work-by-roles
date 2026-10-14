# SPEC-009 · 意图识别推理与受控 Agent Loop（补充方案落地）

> 输入：用户补充设计方案（意图识别 & Agent Loop）· 目标版本：**2.1.0**
> 顶层范式不变：Coordinator 拆解 → 专家并行 → Verifier 复核 → 分歧 HITL。意图推理是 Coordinator **内部**子模块；Loop 仅两类受控形态，**禁止**顶层无限循环。

## 0. 现状差距分析（依据 V2.0 现状）

| 补充要求 | 现状 | 本迭代动作 |
|---|---|---|
| 意图推理流水线（Coordinator 内） | 无 | **新建** `core/orchestration/intent.py` |
| 类型A 单角色内部推理 Loop | 无 | **新建** `core/orchestration/inner_loop.py` |
| 类型B 辩论 Loop | V2.0 `DebateModerator` 已有轮次封顶/让步终止/结构化输出/历史留存 | **合规升级**：每轮 Verifier 收敛评估 + 超限强制终止转 HITL 标记 |
| 控制参数入契约 | 契约无相关字段 | **增量可选字段** `intent_policy` / `inner_loop`（向后兼容，旧 JSON 可加载） |
| Harness 专项指标 | 无 | **新建** `core/harness/loop_metrics.py`（意图/Loop/辩论三组） |
| 推理 trace/审计 | 审计总线/链已有 | 意图与 Loop 每步发 `INTENT_REASONING` / `LOOP_STEP` 事件（枚举扩展） |

## 1. 意图推理流水线 `core/orchestration/intent.py`

```python
IntentType(StrEnum): STANDARD_REVIEW / MISSING_INFO / OUT_OF_SCOPE / AMBIGUOUS / LIGHTWEIGHT_QUERY
NextAction(StrEnum): run_disassemble / ask_user / reject / lightweight_single_expert
IntentPolicy(可选契约字段): confidence_threshold=0.6, allow_lightweight=False,
                            ambiguous_to_hitl=True, custom_rules: dict[str,str]
IntentReasoningStep(step, decision, detail)          # 推理理由链节点
IntentResult: intent_type / confidence / extracted_factors{goal,deliverables,constraints,
               time_limits,preferences} / reasoning_trace: list[IntentReasoningStep]
             / next_action / sanitized_input / policy_snapshot
IntentPipeline(*, contract(coordinator), invoker, detector=None, redactor=None, audit=None):
    run(user_input) -> IntentResult
```

固定顺序（红线：不得跳过、不得自由 prompt 猜测）：
1. **清洗与安全过滤**：复用 `guard_user_input`（高危注入 → OUT_OF_SCOPE/reject，写审计）
2. **意图分类推理**：契约驱动的结构化输出（`intent_type/confidence/factors/reasoning`），经契约 Schema 校验；分类集合固定五类
3. **置信度阈值判定**：低于 `confidence_threshold` → 降级 AMBIGUOUS/ask_user（阈值来自 `IntentPolicy`）
4. **要素抽取**：goal/deliverables/constraints/time_limits/preferences
5. **冲突检测**：抽取要素 vs Coordinator 契约禁区（关键词命中 → OUT_OF_SCOPE/reject）
6. **决策输出**：next_action 映射（STANDARD→run_disassemble；MISSING_INFO/AMBIGUOUS→ask_user；OUT_OF_SCOPE→reject；LIGHTWEIGHT→lightweight_single_expert，仅当 `allow_lightweight`）
- 全程发 `INTENT_REASONING` 审计事件（含 reasoning_trace 摘要）；`policy_snapshot` 记录所用策略（防"事后改阈值"不可追溯）。
- **不做 NLP 模型训练**，全部契约 Prompt 驱动（Invoker 注入）。

## 2. 类型A 单角色内部推理 Loop `core/orchestration/inner_loop.py`

```python
InnerLoopConfig(可选契约字段): max_rounds=3, exit_when: "evidence_sufficient"|"converged",
                               loop_quota_tokens=4000, on_quota_exhausted: "escalate_hitl"|"force_exit"
LoopRound(round_no, conclusion, evidence: list[str], continue_loop: bool, reason)
LoopSummarySnapshot(role_id, rounds_used, conclusion, evidence, stopped_because:
                    evidence_satisfied|max_rounds_risk|quota_exhausted_hitl|quota_exhausted_exit, token_used)
InnerLoopExecutor(*, contract(expert), invoker, memory=None, cache=None, meter=None,
                  config=None(缺省读 contract.inner_loop), audit=None):
    run(sub_question, *, session_id) -> LoopSummarySnapshot
```
- 每轮：编译（契约+已积累证据）→ invoke → 结构化解析 `{conclusion, evidence[], continue_loop, reason}` → Schema 校验 → 审计 `LOOP_STEP`。
- 退出三选一（红线）：`evidence_sufficient` / 达到 `max_rounds`（标记 `max_rounds_risk`）/ `loop_quota_tokens` 耗尽（`escalate_hitl` 或 `force_exit`，由契约配置）。
- 循环内记忆：只写本角色 `ROLE_SESSION`（契约权限门复用）；输出**快照摘要**而非原始消息（控上下文膨胀）。
- 缓存：相同子问题+证据快照命中 `ContractBoundCache` 直接跳过循环。
- token 计量走注入的 `TokenMeter`（独立 `loop_quota_tokens` 预算）。

## 3. 契约增量可选字段（向后兼容）

```python
class RoleContract(...):
    intent_policy: IntentPolicy | None = None      # 仅 Coordinator 语义使用
    inner_loop: InnerLoopConfig | None = None      # 仅 Expert/Verifier 语义使用
```
- 有默认值 None，旧契约 JSON 完全兼容；**内容哈希包含这两个字段**（配置即契约，改阈值=改契约=Diff 可见+缓存失效，符合规则3/4）。
- 跨字段校验：`intent_policy` 仅 coordinator 角色应携带（非硬阻断，Diff 报 HIGH 提示）； DebateConfig 同理走模板配置。

## 4. 辩论 Loop 合规升级（`DebateModerator` 增量）

- `DebateConfig` 增 `referee_evaluates_convergence: bool = True`。
- 每轮结束后由 referee（Verifier 契约）输出收敛评估 `{converged: bool, degree: float, reason}`（结构化、经 Schema 校验、入审计）；converged 即提前终止。
- `max_rounds` 打满未收敛 → `escalated_to_hitl = True`（保留全部分歧记录）。
- `DebateResult` 增 `convergence_evaluations: list`、`escalated_to_hitl: bool`。

## 5. Harness 指标扩展 `core/harness/loop_metrics.py`

```python
IntentMetrics.from_results(results: list[IntentResult], expected: list[IntentType]|None)
  → accuracy / false_reject_rate / ambiguous_detection_rate
LoopMetrics.from_snapshots(snapshots: list[LoopSummarySnapshot], *, quota_tokens)
  → avg_rounds / timeout_rate(max_rounds_risk 占比) / loop_token_ratio(需主任务 token 对比参) / escalate_rate
DebateLoopMetrics.from_results(results: list[DebateResult])
  → convergence_rate / round_limit_exceeded_rate(=escalated_to_hitl 占比)
```

## 6. 验收标准 → 测试映射（tests/wbr/phase8/）

| 验收标准 | 测试 |
|---|---|
| 五类意图分类→next_action 映射正确；reasoning_trace 强制留存；审计事件 | `test_intent_pipeline.py` |
| 置信度低于阈值降级 AMBIGUOUS/ask_user；阈值/开关全部来自 IntentPolicy（零硬编码） | 同上 |
| 越界请求（注入/禁区命中）→ reject 且审计 | 同上 |
| allow_lightweight=False 时 LIGHTWEIGHT 不放行 | 同上 |
| 契约增量字段：旧 JSON 兼容；字段入哈希（改动=新 hash=Diff 可见）；旧契约（无字段）加载不受影响 | `test_contract_loop_fields.py` |
| InnerLoop：证据充足退出/max_rounds 风险标记/quota 耗尽 HITL 升级/快照摘要输出（不含原始消息） | `test_inner_loop.py` |
| 循环缓存命中跳过；循环记忆只写本角色 | 同上 |
| 辩论合规：每轮收敛评估/提前收敛终止/max_rounds 超限 escalated_to_hitl | `test_debate_hitl.py` |
| 三组指标计算正确 | `test_loop_metrics.py` |
| 全量回归 + 新模块覆盖率 ≥90% | PHASE8 报告 |

## 7. 红线复核（每条对应防回归测试）
- 顶层流程不改无限 Loop → ReviewSession 现有测试不变绿转红即回归失败
- 结构化意图输出强制 → IntentPipeline 无 Schema 校验通过路径
- Loop 不脱契约约束 → InnerLoopConfig 缺省读契约字段，无"无上限"构造
- 中间过程必审计 → 断言每轮 LOOP_STEP 事件存在
