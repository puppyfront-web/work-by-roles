# SPEC 文档索引（SDD 设计资产）

> 本目录是 work-by-roles 专家团治理系统的全部设计规格（SDD：Spec-Driven Development）。
> 实施采用 TDD：先测试后实现，全部验收证据见 docs/acceptance/。

| 文档 | 内容 |
|---|---|
| [SPEC-000-全局架构与总则](SPEC-000-全局架构与总则.md) | 定位、三层架构、模块清单（阶段映射）、15 项全局设计决策（D-01~D-15）、强制约束 |
| [SPEC-001-阶段0-基础架构](SPEC-001-阶段0-基础架构.md) | 目录/打包/异常/Trace/配置/日志/审计总线 |
| [SPEC-002-阶段1-核心契约内核](SPEC-002-阶段1-核心契约内核.md) | RoleContract 最终版、编译器、Diff、审计模型、四层记忆、会审流程 |
| [SPEC-003-阶段2-LangGraph适配层](SPEC-003-阶段2-LangGraph适配层.md) | 3 行接入 WBRGuard、拦截器、工具权限、HITL、Checkpointer、安全 V1、Token 治理 |
| [SPEC-004-阶段3-Harness与缓存](SPEC-004-阶段3-Harness与缓存.md) | 黄金用例库、基线快照、回归引擎、六项指标、AI Judge 钩子、契约绑定缓存、审计包 |
| [SPEC-005-阶段4-API与画布](SPEC-005-阶段4-API与画布.md) | FastAPI 路由、任务队列、画布 MVP、错误规范 |
| [SPEC-006-阶段5-V1.0发布](SPEC-006-阶段5-V1.0发布.md) | 官方模板库、文档、PyPI 打包、性能加固 |
| [SPEC-REVIEW](SPEC-REVIEW.md) | 规格自审核记录：覆盖矩阵、八规则合规、17 项问题裁定（R1~R17） |

## 计划与用例

- 开发主计划：[docs/plan/PLAN-MASTER.md](../plan/PLAN-MASTER.md)（阶段闸口、TDD 约定、风险对策）
- 测试用例设计：[docs/plan/TESTCASES.md](../plan/TESTCASES.md)（62 项 ★ 必测 + 全量用例表）

## 验收报告

[docs/acceptance/](../acceptance/)：PHASE0 ~ PHASE5 逐阶段验收（标准→测试映射 + 实测证据）与 FINAL 全量回归报告。

## 变更纪律

SPEC 批准后如需变更，必须在 SPEC-REVIEW.md 追加变更记录并同步受影响的验收标准。
