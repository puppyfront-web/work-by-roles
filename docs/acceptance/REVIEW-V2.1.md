# 代码 Review 与优化报告（V2.1 → V2.1.1）

> 日期：2026-10-14 · 范围：SPEC-009（意图推理/受控Loop）全量落地代码 + 全库静态复审
> 工具：ruff（F/E9/RUF/PLW/UP/ISC 规则族）+ 人工逐模块走查 · 结论：**优化完成，交付**

## 1. 静态复审结果

| 类别 | 数量 | 处置 |
|---|---|---|
| F401 未用导入 | 33+ | 自动修复 |
| I001/RUF022 导入与 `__all__` 排序 | 25 | 自动修复 |
| UP035/UP037 过时/引号注解 | 55 | 自动修复 |
| RUF100 失效 noqa | 7 | 修复（含 2 处格式非法的 noqa 指令重写） |
| **F821 未定义名（潜在运行时炸弹）** | 3 | **手工修复**：engine.py `ReviewResult`×2、metrics.py `CaseResult`（TYPE_CHECKING 导入缺失，`get_type_hints` 场景会炸） |
| **PLW2101 无效锁（真实并发缺陷）** | 2 | **手工修复**：`AuditTrail` 原 `with threading.Lock()` 每次新建锁形同虚设 → 实例级 `RLock` 字段 |
| F811 重复定义 | 2 | 修复（inner_loop 本地 LOOP_SCHEMA 与 loop_config 导入重复；debate ModelRequest 重复导入） |
| F841 未用变量 | 2 | 清理 |
| RUF012 可变类属性 | 2 | `ClassVar` 注解（diff.py 对齐表） |
| ISC004 隐式字符串拼接 | 1 | 加括号 |

复审后门禁：`ruff check --select F,E9` **全部通过**；全量测试 **356 passed / 1 skipped**。

## 2. 人工 Review 发现与处置

| # | 发现 | 严重级 | 处置 |
|---|---|---|---|
| H1 | `AuditTrail` 锁失效（PLW2101）——并行专家写审计存在竞态 | **高** | 已修（实例 RLock + pydantic exclude） |
| H2 | F821 三处（类型注解依赖 `from __future__` 掩盖） | 中 | 已修 |
| H3 | Bundle `suite()`/`baseline()` 方法被同名字段遮蔽 | 中 | 阶段7 TDD 已捕获并修复（`get_suite/get_baseline`），复审确认 |
| H4 | SPEC-009 §4.4 完整性缺口：`LoopSummarySnapshot` 未接入 ReviewSession 主流程 | 中 | **已闭环**：`run(loop_snapshots=...)` 按角色注入专家证据通道（evidence 段），集成测试断言快照结论进入专家编译 prompt |
| H5 | `_DemoInvoker` 直接替换实例方法（弱契约） | 低 | 记录：属演示实现，生产走 Protocol 注入，不改动 |
| H6 | S110/S112/BLE001（总线/桥/循环内的兜底 except） | 设计取舍 | 保留——"可观测层/审计层绝不反噬业务流"（D-14/SPEC-001），均有注释与计数/日志语义 |

## 3. SPEC-009 完整性终检

- 六步意图流水线 / 类型A内循环 / 契约增量字段 / 辩论合规 / 三组指标：全部落地且有具名测试。
- 新闭环：内循环快照 → `ReviewSession.run(loop_snapshots=...)` → 专家 evidence 通道（补 H4）。
- 红线五条防回归测试全部在位且通过。

## 4. 交付状态

- 版本：2.1.1（补丁级：优化与缺陷修复，无 API 变更）
- 测试：356 passed / 1 skipped（真实 Redis 门控）；`ruff check --select F,E9` 全绿
- 回归：存量失败清单与基线零差异（历史验证，本轮未触碰存量包）
