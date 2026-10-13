# SPEC-000 · work-by-roles 专家团系统 · 全局架构与总则

> 状态：已审核通过（见 [SPEC-REVIEW.md](SPEC-REVIEW.md)）
> 版本基准：V1.0.0 目标；阶段映射 0→架构基座、1→V0.1、2→V0.2、3→V0.3、4→V0.4、5→V1.0
> 开发方法论：SDD（本规格驱动）+ TDD（先测试后实现，模块粒度 RED→GREEN）

---

## 1. 项目定位（不可变更）

契约驱动、会审范式原生、带原生 Harness 质量门禁的**开源专家团治理系统**。

- **不是**通用工作流平台（不卷 Dify/Coze）
- **不是**底层调度框架（不卷 CrewAI/AutoGen/LangGraph）
- **可以**作为增强层嵌入已有 LangGraph 系统
- **可以**独立运行完整专家会审平台

核心差异化能力（全部必须落地）：角色契约、权责隔离、独立复核、分歧留存、多层隔离记忆、Token 治理、缓存治理、安全防注入、原生 Harness 评估、全链路审计、可回归验收。

## 2. 三层架构（固定不变）

```
┌─────────────────────────────────────────────────────┐
│  App 层  wbr/app/                                    │
│  FastAPI 服务 · 专家画布(SPA) · 异步任务队列 · 审计导出 │
├─────────────────────────────────────────────────────┤
│  Adapter 层  wbr/adapters/                           │
│  LangGraph 适配器 · Redis 存储后端 · 模型接入封装      │
├─────────────────────────────────────────────────────┤
│  Core 内核  wbr/core/                                │
│  契约 · 编译器 · Diff · 审计 · 记忆 · 编排 · 安全      │
│  Token 治理 · 缓存 · Harness（纯逻辑、框架无关）       │
└─────────────────────────────────────────────────────┘
```

依赖方向强制：`app → adapters → core`，禁止反向依赖；core 内部禁止 import adapters/app。

### 2.1 全局固定模块清单（锁定，与方案的模块清单一一对应）

| 模块 | 归属层 | 落地阶段 | 代码位置 |
|---|---|---|---|
| RoleContract 契约模型 | Core | 阶段1 | `wbr/core/contract/models.py` |
| Prompt 编译器 | Core | 阶段1 | `wbr/core/contract/compiler.py` |
| 契约版本 Diff | Core | 阶段1 | `wbr/core/contract/diff.py` |
| 基础审计模型 | Core | 阶段1 | `wbr/core/audit/models.py` |
| 四层隔离记忆 | Core | 阶段1 | `wbr/core/memory/` |
| 最简会审编排 | Core | 阶段1 | `wbr/core/orchestration/` |
| 安全防注入 V1 | Core | 阶段2 | `wbr/core/security/` |
| Token 全链路治理 | Core | 阶段2 | `wbr/core/token/` |
| LangGraph 适配器 | Adapter | 阶段2 | `wbr/adapters/langgraph/` |
| 记忆持久化(Redis) | Adapter | 阶段2 | `wbr/adapters/storage/` |
| Harness 评估体系 | Core | 阶段3 | `wbr/core/harness/` |
| 契约绑定语义缓存 | Core | 阶段3 | `wbr/core/cache/` |
| 标准化审计包导出 | Core | 阶段3 | `wbr/core/audit/pack.py` |
| API 服务 | App | 阶段4 | `wbr/app/api/` |
| 专家画布 MVP | App | 阶段4 | `wbr/app/canvas/` |
| 异步任务队列 | App | 阶段4 | `wbr/app/tasks/` |
| 官方契约模板库 | App/资源 | 阶段5 | `wbr/templates/teams/` |

**V1.x / V2.0 预留（本交付内禁止实现）**：MCP 接入层、角色独立知识库、OpenTelemetry 可观测、高级语义缓存、内容脱敏、基线 Bundle、灰度 A/B、多 Workspace、审计哈希链、受控辩论。

## 3. 全局设计决策（审核定案）

| # | 决策 | 内容与理由 |
|---|---|---|
| D-01 | Core 依赖策略 | Core 仅允许 **stdlib + Pydantic V2**。方案同时要求"Core 无第三方依赖"与"全程 Pydantic V2"，二者冲突；裁定 Pydantic V2 为契约模型的唯一许可依赖，其余第三方（LangGraph/Redis/FastAPI/PyYAML）一律置于 Adapter/App 层。JSON Schema 校验器在 Core 内自研子集实现（见 D-08） |
| D-02 | 存量代码共存 | 新系统以独立顶层包 `wbr` 落地于本仓库；存量 `work_by_roles` 包**原样保留、禁止修改**，其 156 项存量单测作为回归基线持续通过。PyPI 发行名保持 `work-by-roles`，同时打包 `wbr` 包 |
| D-03 | Python 版本 | `requires-python >= 3.10`（LangGraph 与现代 Pydantic V2 的交集）；开发/验证环境 Python 3.13 |
| D-04 | Redis 可测性 | `StorageBackend` 协议定义于 Adapter 层，`RedisStorageBackend` 接受可注入的 redis 客户端；测试默认使用进程内 Fake 实现，真实 Redis 集成测试以环境变量 `WBR_TEST_REDIS` 门控，缺失则跳过 |
| D-05 | 专家并行 | Core 编排使用 `ThreadPoolExecutor` 并行执行专家，结果按契约 ID 排序保证确定性；异常专家不阻断整场会审，降级记录为 failed 状态 |
| D-06 | 模型接入 | Core 定义 `ModelInvoker` Protocol（`invoke(request) -> ModelResponse`），Core 永不发起真实网络调用；示例使用脚本化 Invoker；Adapter 层负责对接真实模型 |
| D-07 | Token 计量 | Core 内置确定性启发式计数器（CJK≈1 token/字、拉丁≈1 token/4 字符，向上取整）；tiktoken 精确计量留待 V1.x，通过 `TokenCounter` 协议可替换 |
| D-08 | Schema 校验 | Core 自研 JSON Schema **子集**校验器（type/properties/required/items/enum/minimum/maximum/minLength/maxLength/additionalProperties），零依赖、可 100% 测试；Adapter 层可选启用 `jsonschema` 全量校验增强 |
| D-09 | 内容哈希 | 所有哈希 = `sha256(canonical_json(obj))`；canonical_json：排序键、`ensure_ascii=False`、无空白分隔符。契约 hash 变更 ⇒ 缓存自动失效 |
| D-10 | 画布形态 | 极简 SPA（原生 JS + SVG），由 FastAPI 静态托管，**零 Node 构建链**；画布仅消费 API，不耦合内核（规则 8） |
| D-11 | 异步队列 | V0.4 采用进程内 `TaskQueue` 抽象（asyncio + JSON 落盘恢复），接口预留外部 broker 替换点；Celery/Redis 队列留待后续版本 |
| D-12 | HITL | Core 定义框架无关审批状态机（PENDING→APPROVED/REJECTED/ESCALATED）；Adapter 层映射到 `langgraph.interrupt()`/`Command(resume=)` |
| D-13 | 版本管理 | 包版本随阶段推进：0.1.0 → 0.2.0 → 0.3.0 → 0.4.0 → 1.0.0；契约模型带独立 semver + 内容哈希，双方独立演进 |
| D-14 | 审计总线 | 同步进程内 pub/sub，有界队列、溢出丢弃并计数（绝不阻塞业务流）；阶段0 为通用事件，阶段1 升级为强类型审计事件 |
| D-15 | 配置加载 | `WBRConfig`（Pydantic）定义于 Core；YAML 解析器位于 `wbr/config_loader.py`（内核之外），PyYAML 缺失时报可诊断错误 |

## 4. 全局强制约束（每阶段验收均须复核）

1. 严格按阶段顺序开发，不跳阶段、不超前实现 V1.x/V2.0 内容。
2. 每阶段交付物齐全：代码 + 单元测试 + 示例 + 文档 + 验收自测报告。
3. 所有策略/权限/规则声明式写入 RoleContract，禁止业务硬编码。
4. Adapter 层失败可降级：`WBRGuard` 全链路异常不吞不炸——校验失败产生审计事件与结构化拦截结果，是否阻断由契约声明决定。
5. 全链路可观测：任何角色行为均产生 TraceID 关联的审计事件。
6. 核心模块（core/contract、core/memory、core/security、core/cache、core/harness、core/token）单元测试行覆盖率 ≥ 90%。
7. 存量 `work_by_roles` 测试套件全程保持通过（回归保护）。

## 5. 目录规划（阶段0 建立，全阶段填充）

```
wbr/
├── __init__.py                 # __version__, 公共 API 再导出
├── core/
│   ├── exceptions.py  context.py  constants.py  config.py
│   ├── logging.py     audit_bus.py
│   ├── contract/      models.py compiler.py diff.py
│   ├── audit/         models.py trail.py pack.py(阶段3)
│   ├── memory/        base.py layers.py hub.py
│   ├── orchestration/ invoker.py session.py coordinator.py verifier.py review.py
│   ├── security/      guard.py boundaries.py
│   ├── token/         counter.py meter.py budget.py
│   ├── cache/         backends.py contract_cache.py
│   ├── schema/        validator.py(自研子集校验)
│   └── harness/       cases.py baseline.py engine.py metrics.py judge.py
├── adapters/
│   ├── langgraph/     mapping.py state.py interceptors.py guard.py hitl.py builder.py
│   └── storage/       base.py memory_backend.py redis_backend.py
├── app/
│   ├── api/           main.py routes_contracts.py routes_review.py routes_harness.py routes_audit.py schemas.py
│   ├── tasks/         queue.py worker.py store.py
│   └── canvas/        static/ (index.html app.js style.css)
├── config_loader.py
└── templates/teams/   arch_review_team/ security_audit_team/   (阶段5)
tests/wbr/              # 新系统测试（阶段对齐分目录）
examples/               # 每阶段示例
docs/spec/  docs/plan/  docs/acceptance/
```

## 6. 验收证据规范

每阶段产出 `docs/acceptance/PHASE<N>.md`，必须包含：验收标准逐条核对表、实际执行的 pytest 命令与结果摘要（用例数/通过数/覆盖率）、遗留问题清单。最终交付执行全量回归（存量 + 新系统全部测试）并出具 `docs/acceptance/FINAL.md`。
