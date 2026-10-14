# 阶段8 验收报告（PHASE8 · V2.1 意图推理与受控 Loop）

> 日期：2026-10-14 · 依据：SPEC-009（补充方案落地）· 版本：2.1.0 · 结论：**通过**

## 0. 现状差距收敛（补充方案 vs 落地）

| 补充要求 | 状态 |
|---|---|
| 意图推理流水线（六步固定顺序、结构化输出、理由链审计、阈值入契约） | ✅ 全部落地 |
| 类型A 单角色内循环（轮次/配额/退出三选一/快照输出/缓存/审计） | ✅ 全部落地 |
| 类型B 辩论 Loop | V2.0 已有主体，本迭代补齐每轮收敛评估 + 超限升级 HITL |
| 契约增量字段 intent_policy / inner_loop | ✅ 向后兼容 + 纳入内容哈希（Diff 可见） |
| Harness 三组专项指标 | ✅ IntentMetrics / LoopMetrics / DebateLoopMetrics |
| 红线清单五条 | 全部有防回归测试（见下） |

## 1. 验收标准核对

| SPEC-009 验收标准 | 证据 | 结果 |
|---|---|---|
| 五类意图 → next_action 映射；reasoning_trace 强制；INTENT_REASONING 审计含策略快照 | `test_intent_pipeline.py` 10 用例 | ✅ |
| 置信度降级（0.95<0.99→AMBIGUOUS）；阈值/开关全部来自 IntentPolicy | `test_thresholds_come_from_policy_not_hardcoded` | ✅ |
| 高危注入第 1 步拦截 → reject，未触达 LLM；安全过滤 trace 留存 | `test_injection_input_rejected_before_llm` | ✅ |
| allow_lightweight 门控（默认 False 回退标准会审） | `test_lightweight_gate_by_policy` | ✅ |
| LLM 输出不合规 → 安全降级 AMBIGUOUS 不抛异常 | `test_llm_output_schema_violation_fails_safe` | ✅ |
| 旧契约 JSON 兼容；新字段进哈希且 Diff=POLICY；序列化往返 | `test_contract_loop_fields.py` 4 用例 | ✅ |
| 内循环：证据充足退出/上限风险标记/配额耗尽 HITL·强制退出/快照字段最小化/缓存跳过/角色私有记忆/每轮审计 | `test_inner_loop.py` 9 用例 | ✅ |
| 辩论：每轮收敛评估/提前收敛终止/超限 escalated_to_hitl/评估不合规保守未收敛/旧语义开关 | `test_debate_hitl.py` 6 用例 | ✅ |
| 三组指标（含误拒率、模糊识别率、超时率、token 占比、收敛率） | `test_loop_metrics.py` 4 用例 | ✅ |
| 全量回归 + 新模块覆盖率 ≥90% | 355 passed / 1 skipped；intent 90% / inner_loop 96% / loop_metrics 100% | ✅ |

## 2. 红线复核（防回归证据）

| 红线 | 防回归证据 |
|---|---|
| 会审主流程不改无限 Loop | phase1 全部会审流程测试原样通过（ReviewSession 零改动） |
| 禁止自由 prompt 猜意图 | IntentPipeline 强制 Schema 校验，`test_llm_output_schema_violation_fails_safe` 证明无合法输出即降级 |
| Loop 不脱契约约束 | InnerLoopConfig 只能来自参数或契约字段；`test_contract_default_config_used` 证明契约字段生效 |
| 中间过程必审计 | `test_loop_memory_only_role_session_and_audited_per_round` 逐轮 LOOP_STEP 断言 |
| 阈值零硬编码 | `test_thresholds_come_from_policy_not_hardcoded` + policy_snapshot 可追溯 |

## 3. 交付物清单
- Core：`wbr/core/orchestration/{intent,inner_loop}.py`、`wbr/core/loop_config.py`（叶子配置模块，避免循环导入）、`wbr/core/harness/loop_metrics.py`；`contract/models.py` 增量可选字段；`audit/models.py` 枚举扩展（INTENT_REASONING/LOOP_STEP）
- 测试：`tests/wbr/phase8/`（6 文件 32 用例）
- 文档：SPEC-009 + REVIEW §8（R30~R35）、README 能力表、版本 2.1.0

## 4. 遗留事项
- 意图分类与内循环判定的"智能"部分由注入的 Invoker 承载（契约 Prompt 驱动），Core 无 NLP 依赖（与补充方案一致）。
- 辩论收敛评估同样为 Invoker 驱动（Verifier 契约），评估不合规保守视为未收敛。
