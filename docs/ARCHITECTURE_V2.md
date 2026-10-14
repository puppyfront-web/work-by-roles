# work-by-roles 专家团治理系统 · V2.1.1 架构设计方案

> 状态：与代码同步（V2.1.1）· 上游规格：docs/spec/SPEC-000~009 · 验收证据：docs/acceptance/

---

## 1. 系统定位

**契约驱动、会审范式原生、带原生 Harness 质量门禁的开源专家团治理系统。**

三条顶层原则（贯穿全部设计）：

1. **契约优先**：一切角色行为约束（职责 SOP、禁区、输出 Schema、证据规范、工具白名单、记忆权限、Token 配额、意图策略、循环参数）声明式写入 `RoleContract`，版本化 + 内容哈希定版，禁止业务硬编码。
2. **会审主流程不变式**：`Coordinator 拆解 → 多专家并行 → Verifier 复核 → 分歧留存/升级 HITL` 是 DAG 状态机；意图推理是 Coordinator 内部子模块，Agent Loop 只存在于"单角色内部"与"受控辩论"两种受控形态，**顶层永不无限循环**。
3. **分层纯净**：Core 仅依赖 stdlib + Pydantic V2（AST 静态扫描测试守护）；所有第三方（LangGraph/MCP/Redis/OTel/FastAPI）隔离在 Adapter/App 层，且全部可选、缺失给安装指引。

## 2. 分层架构总图

```
┌────────────────────────────────────────────────────────────────────────┐
│ App 层  wbr/app/                                                       │
│  ├ api/        FastAPI 服务（契约CRUD/会审调度/Harness回归/审计导出/画布托管）│
│  ├ canvas/     专家画布 SPA（拖拽建团/契约编辑/运行/分歧红色高亮，零构建）      │
│  ├ tasks/      TaskQueue 协议：InProcessTaskQueue(asyncio) / Inline /      │
│  │             JsonTaskStore 落盘恢复（DONE可查、PENDING重投递）             │
│  ├ store.py    ContractRegistry（契约 CRUD + 全版本快照 + Diff）           │
│  └ workspace.py 多 Workspace 隔离（契约/用例/任务/记忆四维，跨域显式复制带血缘）│
├────────────────────────────────────────────────────────────────────────┤
│ Adapter 层  wbr/adapters/    （全部可选依赖，惰性导入）                    │
│  ├ langgraph/  WBRGuard 3行接入存量图 · 拦截器 · HITL(interrupt/Command)   │
│  │             · build_review_graph 原生会审图 · Checkpointer 兼容         │
│  ├ mcp/        MCPToolBridge（白名单前置+二阶防护+脱敏）· StdioMCPClient    │
│  ├ storage/    InMemory/Redis 存储后端 · 持久化记忆门面 · RedisCacheBackend│
│  └ observability/  OTelBridge：审计总线 → OTel span/指标（零侵入订阅）      │
├────────────────────────────────────────────────────────────────────────┤
│ Core 层  wbr/core/    （仅 stdlib + Pydantic V2，框架无关、无网络调用）     │
│  contract/   RoleContract · ContractCompiler · ContractDiffEngine         │
│  schema/     自研 JSON Schema 子集校验器（零依赖）                          │
│  orchestration/  ReviewSession(会审状态机) · IntentPipeline(意图推理)      │
│                  · InnerLoopExecutor(类型A受控内循环) · DebateModerator    │
│                  · HITL审批状态机 · ModelInvoker协议/ScriptedInvoker       │
│  memory/     四层隔离记忆（role_static/role_session/task_scratch/global）  │
│  security/   注入检测规则库 · 边界隔离符 · 内容脱敏Redactor · 风控策略       │
│  token/      启发式计数 · 三维计量(TokenMeter) · 预算降级(TokenBudget)      │
│  cache/      ContractBoundCache(精确) · SemanticCache(语义) · LRU后端      │
│  knowledge/  角色独立知识库（权限锚定记忆层，检索接 evidence 通道）           │
│  harness/    回归引擎 · 基线快照 · 六项指标 · AI Judge 钩子 · 反馈闭环      │
│              · IntentMetrics/LoopMetrics/DebateLoopMetrics                │
│  audit/      强类型事件 · AuditTrail · 审计包导出 · 防篡改哈希链            │
│  bundle/     基线 Bundle（契约+用例+基线三位一体，manifest 双层校验）        │
│  experiment/ 灰度 A/B（确定性分流 + 三级保守裁决）                          │
│  loop_config/canonical/constants/context/config/exceptions/logging       │
├────────────────────────────────────────────────────────────────────────┤
│ 资源  wbr/templates/teams/  arch_review_team · security_audit_team        │
│ CLI   wbr.cli  →  wbr version / list-teams / show-team / run-team         │
└────────────────────────────────────────────────────────────────────────┘
依赖方向强制：App → Adapter → Core，禁止反向与跨层（结构测试 + AST 扫描双重守护）
```

## 3. 核心运行时流程

### 3.1 主会审流程（不变式）

```
用户问题
   │
   ▼
┌─────────────────── Coordinator（内部含意图推理流水线）──────────────────┐
│ 1 安全过滤(guard) → 2 意图分类(契约Prompt+Schema校验) → 3 置信阈值判定    │
│ 4 要素抽取 → 5 冲突检测(禁区比对) → 6 决策                              │
│   next_action: run_disassemble │ ask_user │ reject │ lightweight_single │
└──────────────┬─────────────────────────────────────────────────────────┘
               ▼ run_disassemble
   ┌───────── Coordinator 拆解：assignments[{expert, sub_question}] ─────────┐
   ▼                                                                        ▼
专家1 ┌──────────── 单角色内部受控循环（可选，契约 inner_loop）───────────┐ 专家2 …
     │ 推理→证据不足→MCP/检索→再推理…                                    │
     │ 退出三选一：证据充足 / max_rounds(标记风险) / loop配额耗尽(转HITL)  │
     │ 每轮 LOOP_STEP 审计 · 角色私有记忆 · 缓存命中跳过                    │
     └──────────────► 输出【快照摘要】进主流程（原始消息不灌入）◄──────────┘
   │
   ▼ 全部专家输出 → Schema 校验 + 禁区检测 + 证据完备检查（strict 违规=FAILED）
   │
   ├─► 分歧检测：同子问题 conclusion 冲突 → Disagreement（留存不仲裁）
   │        └─► 受控辩论（V2.1 合规）：轮次封顶 · 每轮 Verifier 收敛评估
   │                · 未收敛 escalated_to_hitl=True
   ▼
Verifier 独立复核（ReviewCriteria 多维评分）
   ▼
final_answer（通过=综合结论；未通过=标注复核意见）
   │
   ▼ 全链路审计：INTENT_REASONING / LOOP_STEP / SCHEMA_VIOLATION /
              FORBIDDEN_VIOLATION / VERIFIER_VERDICT / REVIEW_COMPLETED …
```

### 3.2 质量门禁回路（Harness 闭环）

```
黄金用例库 CaseSuite ──► 基线快照（契约哈希+用例哈希+模型指纹锁定）
        │                        │
        ▼                        ▼
  RegressionEngine.run_suite ──► RegressionReport（六项指标 + AI Judge 分）
        │                          │
        ▼                          ▼
  改契约（Diff 可见）◄──── compare_with：能力退化自动检测（阈值 -0.05）
        │
        └─► 契约变更 ⇒ 语义/精确缓存自动失效（Key 绑定契约哈希）
线上负反馈 ──► FeedbackLoop ──► down 聚合为黄金用例 ──► 回归（闭环）
```

## 4. 关键设计决策（定案，含裁定编号）

| 决策 | 内容 |
|---|---|
| D-01 Core 依赖 | 仅 stdlib + Pydantic V2；JSON Schema 子集校验器自研；YAML/MCP/OTel 均在层外 |
| D-04 Redis 可测 | 客户端注入协议；测试用同构 Fake，真连测 env 门控 |
| D-05 专家并行 | ThreadPool + TraceContext 显式传递 + role_id 确定性排序；单专家失败降级不阻断 |
| D-06 模型接缝 | `ModelInvoker` 协议是唯一模型入口；Core 无网络调用；测试/示例用 ScriptedInvoker |
| D-08 Schema 校验 | Core 自研子集校验器（98% 覆盖），Adapter 可选 jsonschema 增强 |
| D-09 完整性算法 | canonical JSON（排序键/不转义/紧凑）+ sha256；契约哈希/Bundle/哈希链/审计包统一复用 |
| D-12 HITL | Core 状态机（PENDING→APPROVED/REJECTED/ESCALATED）；Adapter 映射 interrupt/Command(resume) |
| D-14 审计总线 | 有界队列+溢出丢弃计数+订阅者异常自吞——可观测层绝不反噬业务流 |
| R18 知识库权限 | 锚定 ROLE_STATIC 记忆层语义，RoleContract 零改动 |
| R19 语义缓存防脏读 | 契约哈希+证据快照精确一致才允许语义命中 |
| R26 辩论红线 | 受控分歧辩论，unresolved 原样留存，禁止仲裁抹平 |
| R30 契约增量字段 | intent_policy/inner_loop 可选、进内容哈希（改阈值=新版本=Diff 可见=缓存失效） |

## 5. 安全模型（纵深四层）

1. **输入侧**：`InjectionDetector` 中英双语规则库（20+ 攻击样例回归）→ `guard_user_input` 按策略放行/清洗/阻断；
2. **边界侧**：外部内容（工具/MCP 返回）以 `wrap_external_content` 包裹 + 二阶注入扫描 + 边界符转义（编译器同样转义用户输入中的伪造边界）；
3. **权限侧**：FunctionCall/MCP 工具白名单前置（拒绝不触达）；四层记忆读写按契约授权 + 全局写双重确认 + 知识库同源校验；
4. **数据侧**：`Redactor` PII 脱敏（稳定占位符）可挂知识库入库、MCP 返回、审计导出；审计包默认脱敏（摘要+digest）。

## 6. 可观测性

- **事件流**：全部角色行为产生 `TraceID` 关联的强类型审计事件 → `AuditTrail`（进程内）+ `AuditBus`（广播）；
- **防篡改**：`HashChainAuditor` 链式定版（seq+prev_hash），verify 定位断点；
- **导出**：`AuditPackBuilder` 标准审计包（format_version/sessions/events/integrity.content_digest，默认脱敏）；
- **OTel**：`OTelBridge` 订阅总线 → span（含 payload 属性）+ 计数指标（reviews/violations/tokens），enabled 开关，异常自吞。

## 7. 可插拔点汇总（全部有 Protocol + 默认实现 + 测试）

| 扩展点 | 位置 | 默认实现 |
|---|---|---|
| 模型接入 | `ModelInvoker` | ScriptedInvoker（演示）/ LangChain 封装（文档示例） |
| 记忆存储 | `MemoryStore` / `StorageBackend` | InMemory / Redis |
| 缓存后端 | `CacheBackend` | InMemory LRU / Redis |
| 语义向量 | `EmbeddingFn` | 注入（Core 不内置模型） |
| AI 评估 | `JudgeHook` | HeuristicJudge |
| 任务队列 | `TaskQueue` | InProcess(asyncio) / Inline / JSON 落盘 |
| MCP 传输 | `MCPClient` | StdioMCPClient（mcp SDK）/ Fake |
| 可观测 | tracer/meter 注入 | OTel SDK（with_sdk）/ Stub |

## 8. 部署形态

- **SDK 嵌入**：`pip install work-by-roles[langgraph]`，存量 LangGraph 项目 3 行接入（WBRGuard）；
- **独立平台**：`pip install work-by-roles[server]` + `uvicorn --factory wbr.app.api.main:create_app` → API(/api/v1) + 画布(/canvas)；
- **企业多租户**：WorkspaceRegistry 目录级隔离；缓存/记忆可切 Redis 共享；审计包定期归档；
- **数据布局**：`<data_root>/{contracts,suites,tasks,workspaces}`，全部 JSON，重启可恢复。

## 9. 质量门禁（持续有效的工程约束）

| 门禁 | 标准 | 守护方式 |
|---|---|---|
| 测试 | 356 passed / 1 skipped | pytest 全量（48 测试文件，62 ★ 必测项） |
| 覆盖率 | Core 关键模块 ≥90%（现 90–100%，总体 95%） | pytest-cov |
| 依赖纯净 | Core 无第三方框架依赖 | AST 扫描测试 |
| 静态检查 | ruff F/E9 全绿 | CI 命令 |
| 异常统一 | 100% WBRError 子类、无裸 except-pass | AST 扫描测试 |
| 存量回归 | legacy 失败清单与基线零差异 | 每阶段 diff 验证 |
| 分歧红线 | 不仲裁抹平 | 专项测试 |
