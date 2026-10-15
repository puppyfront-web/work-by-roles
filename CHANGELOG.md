# 更新日志（Changelog）

格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；版本遵循语义化。

## [Unreleased]

### Added
- **真实模型一键接入**：`OpenAICompatInvoker`（`wbr/adapters/llm/`）——任何 OpenAI 兼容 `/chat/completions` 端点均可接入（OpenAI / DeepSeek / Kimi / Qwen / GLM / Ollama / vLLM）；三个环境变量 `WBR_LLM_API_KEY` / `WBR_LLM_MODEL` / `WBR_LLM_BASE_URL` 即配置完成；支持按角色覆盖模型（`model_by_role`）、429/5xx 指数退避重试
- **CLI `--live`**：`wbr run-team <team> <question> --live` 走真实模型；缺配置时给出明确指引；默认仍为零依赖演示模式
- **API 自动切换**：`create_app` 检测到 `WBR_LLM_*` 环境变量自动启用真实 Invoker，`/api/v1/healthz` 与画布页头显示当前模式（真实模型/演示模式）
- **画布模板导入**：`GET /api/v1/templates` + `POST /api/v1/templates/{team}/import`；画布左上角一键导入官方专家团模板（已存在的契约自动跳过）

### Docs
- README 中英双语重写：新增受众定位（适合谁/不适合谁）、典型场景表、零到一五步上手指南（演示→真模型→画布→SDK）、自定义专家团最小 YAML 示例、FAQ

## [2.1.1] · 2026-10-14

### Fixed
- **并发缺陷**：`AuditTrail` 的锁在 `with threading.Lock()` 中每次新建、互斥形同虚设 → 改为实例级 `RLock`（并行专家写审计竞态消除）
- **F821 潜在炸弹 ×3**：`harness/engine.py`、`harness/metrics.py` 类型注解引用未导入名（TYPE_CHECKING 补齐）

### Changed
- 全库静态清零：139 项自动修复（未用导入/导入排序/过时注解）+ 12 项手工修复（详见 [REVIEW-V2.1](docs/acceptance/REVIEW-V2.1.md)）
- 刻意保留的兜底 except（总线/桥零反噬设计）逐处留档

### Added
- SPEC-009 §4.4 完整性闭环：`ReviewSession.run(loop_snapshots=...)` 将内循环快照按角色注入专家 evidence 通道

## [2.1.0] · 2026-10-14

### Added（补充方案：意图识别推理 + 受控 Agent Loop）
- **意图推理流水线**（Coordinator 内部子模块）：六步固定顺序（安全过滤→五类意图分类→置信阈值→要素抽取→冲突检测→决策）；`reasoning_trace` 强制留存；`INTENT_REASONING` 审计事件含策略快照；LLM 输出不合规安全降级
- **类型A 单角色内部受控循环**：契约化 `max_rounds/loop_quota_tokens/退出条件`；证据充足退出 / 上限风险标记 / 配额耗尽转 HITL；快照摘要输出；缓存命中跳过；逐轮 `LOOP_STEP` 审计；循环记忆仅角色私有
- **契约增量可选字段** `intent_policy` / `inner_loop`：向后兼容，纳入内容哈希（改阈值 = 新版本 = Diff 可见 = 缓存失效）
- **辩论 Loop 合规升级**：每轮 Verifier 收敛评估；打满轮次 `escalated_to_hitl=True`；评估不合规保守视为未收敛
- **Harness 三组专项指标**：`IntentMetrics`（准确率/误拒率/模糊识别率）、`LoopMetrics`（平均轮次/超时率/Token占比/HITL率）、`DebateLoopMetrics`（收敛率/轮次超限率）

### 红线遵守
会审主流程零改动；意图必须结构化输出；Loop 无法脱离契约约束构造；中间过程全审计——均有防回归测试。

## [2.0.0] · 2026-10-14

### Added（企业版，SPEC-008）
- **防篡改审计哈希链**：seq+prev_hash 链式定版，篡改/删除/乱序检出并定位断点
- **多 Workspace 隔离**：契约/用例/任务/记忆四维隔离，跨域显式复制带血缘
- **受控专家辩论**：仅对已检出分歧、轮次封顶、让步即止、违规禁言、历史不仲裁
- **基线 Bundle**：契约+用例+基线三位一体打包，manifest 双层完整性校验，跨环境迁移
- **灰度 A/B 实验**：确定性分流、变体同构校验、三级保守裁决（并列不切换）

## [1.1.0] · 2026-10-14

### Added（V1.x 生态，SPEC-007）
- 内容脱敏与安全风控（PII 规则库/稳定占位符/三态策略）
- 角色独立知识库（权限锚定记忆层，检索接 evidence 通道）
- 契约绑定语义缓存（契约哈希严格一致前提下的近似命中）
- 反馈闭环（负反馈聚合为黄金用例接入回归）
- MCP 接入层（权限前置+二阶防护+脱敏）
- OpenTelemetry 可观测桥（审计总线零侵入）

## [1.0.0] · 2026-10-14

### Added（首个正式版，五阶段完整交付）
- 三层架构内核：RoleContract 契约模型（版本化+内容哈希）、安全 Prompt 编译器、契约 Diff、四层隔离记忆、纯 Core 会审流程（Coordinator→专家并行→Verifier，分歧留存）
- LangGraph 适配：WBRGuard 3 行接入存量图、输出/禁区拦截器、工具权限门、HITL、Checkpointer 兼容、原生会审图生成
- Harness：黄金用例库、基线快照、批量回归、六项指标、AI Judge 钩子、能力退化检测
- 契约绑定缓存（Key = 契约哈希|问题哈希|证据快照）
- FastAPI 服务 + 异步任务队列 + 专家画布 SPA
- 两套官方专家团模板（架构评审/安全审计）
- Legacy：多角色技能工作流 CLI（`work_by_roles` 包，冻结维护）
