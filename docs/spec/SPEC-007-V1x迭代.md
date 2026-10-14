# SPEC-007 · V1.x 迭代 · 可观测与生态扩展

> 前置：V1.0 已交付（docs/acceptance/FINAL.md）。目标版本：**1.1.0**
> 原方案"V1.x 结构预留，暂不开发"的冻结约束在 V1.0 验收后由迭代指令解除；V2.0 企业版内容仍禁止实现。

## 0. 范围（锁定）

| # | 模块 | 层 | 代码位置 |
|---|---|---|---|
| F1 | 内容脱敏与安全风控 | Core | `wbr/core/security/redactor.py` |
| F2 | 角色独立知识库 | Core | `wbr/core/knowledge/` |
| F3 | 高级缓存语义匹配 | Core | `wbr/core/cache/semantic.py` |
| F4 | 反馈闭环 | Core | `wbr/core/harness/feedback.py` |
| F5 | MCP 接入层 | Adapter | `wbr/adapters/mcp/` |
| F6 | OpenTelemetry 可观测 | Adapter | `wbr/adapters/observability/otel.py` |

**V2.0 仍禁做**：基线 Bundle 打包、灰度 A/B、多 Workspace、审计哈希链、受控辩论。

## 1. F1 内容脱敏与安全风控 `Redactor`

```python
RedactionRule(name, pattern, replacement, description)      # 可扩展
DEFAULT_REDACTION_RULES: email / phone(CN) / id_card(CN) / api_key / credit_card / ipv4
RedactionReport(findings: [{rule, count}], redacted_text, original_digest)
Redactor(rules=None, *, enabled=True):
    redact(text) -> RedactionReport          # enabled=False 原样返回
    redact_obj(obj) -> (obj', report)        # 递归 dict/list 字符串值
RiskControlPolicy(max_injection_risk: RiskLevel=HIGH, pii_action: "redact"|"block"|"off"="redact")
assess_and_redact(text, *, detector, redactor, policy) -> RiskDecision(allowed, action, report, redaction)
```
- 脱敏规则命中即替换为稳定占位符（`[EMAIL_1]` 带序号，同值同占位符）。
- `redact_obj` 用于审计包导出前的内容清洗（与 AuditPackBuilder.include_contents 组合）。
- 全部可关闭（规则6）；不修改既有 guard 行为。

## 2. F2 角色独立知识库 `KnowledgeBase`

```python
KnowledgeDocument(doc_id, role_id, title, content, tags, metadata, created_at)
KnowledgeBase(*, audit=None):
    add(doc, *, contract)                    # 写权限校验：contract.memory_permissions.write_layers 含 ROLE_STATIC（知识库锚定角色静态层），否则 E3001
    search(query, *, role_id, contract, top_k=5) -> list[KnowledgeSearchHit]
    remove(doc_id, *, contract) / documents(role_id)
KnowledgeSearchHit(doc_id, title, score, snippet)
```
- 检索：确定性轻量打分（关键词命中率 + 标题加权 + 标签命中），零依赖、可测试；向量检索留待后续。
- 角色隔离：A 角色契约检索不到 B 角色私有文档；`shared=True` 文档可被任意有读权限的契约检索。
- 与会审集成：`KnowledgeEvidenceCollector(kb)` 产出 `evidence: list[str]` 供编译器（复用既有 evidence 通道），知识来源自动带 `[doc_id]` 引用前缀。

## 3. F3 高级缓存语义匹配 `SemanticCache`

```python
EmbeddingFn(Protocol): embed(text) -> list[float]
SemanticCache(exact: ContractBoundCache, *, embedder, threshold=0.92, enabled=True)
    get(contract, question, evidence, *, semantic=True) -> (value, hit_kind)  # hit_kind: exact|semantic|miss
    put(...)  # 同时写入精确层与向量索引（内存，契约哈希隔离）
    stats -> 兼容 CacheStats + semantic_hits
```
- 语义命中前置条件：**契约哈希必须完全一致** + 证据快照一致；仅问题文本近似。
- 相似度 = 余弦；threshold 可配；embedding 函数注入（Core 不内置模型）。
- 索引驱逐与 exact 层 LRU 联动（契约失效时清空对应索引条目）。

## 4. F4 反馈闭环 `FeedbackLoop`

```python
FeedbackRecord(feedback_id, review_id, trace_id, rating: up|down, comment, reviewer, categories, ts)
FeedbackLoop(*, trail=None, audit=None):
    record(...) -> FeedbackRecord
    stats() -> {total, up, down, down_rate, by_category}
    to_golden_cases(min_samples=3, *, suite_id) -> CaseSuite   # down 反馈按问题聚合 → 黄金用例（回归负样本）
    pending_questions() -> list
```
- down 反馈聚合问题进入 `to_golden_cases`，直接接入既有 RegressionEngine（闭环：线上反馈 → 回归用例 → 契约修正 → 一键回归）。
- 全部事件入审计。

## 5. F5 MCP 接入层 `adapters/mcp/`

```python
MCPClient(Protocol): list_tools() / call_tool(name, arguments)   # 注入协议（mcp SDK / 测试 Fake / 自定义传输）
MCPToolBridge(client, *, gate: ToolPermissionGate, redactor=None, boundaries=True):
    available_tools(contract) -> list[ToolInfo]       # 白名单过滤后的可见工具
    invoke(contract, tool_name, arguments) -> MCPToolResult(allowed, content, error, audits)
```
- 权限前置：未过 ToolPermissionGate 的工具直接拒绝（E8002）；工具返回内容经二阶注入扫描 + `wrap_external_content` 包裹；敏感信息经 Redactor 脱敏（可选）。
- `mcp` SDK 缺失时协议仍可用（MCPClient 可为任意实现）；提供 `StdioMCPClient`（基于 `mcp` SDK，惰性导入，缺失给指引）。
- Core 不感知 MCP：Bridge 只消费 Core 的契约与安全组件。

## 6. F6 OpenTelemetry 可观测 `adapters/observability/otel.py`

```python
OTelBridge(*, tracer=None, meter=None, enabled=True):
    attach(bus: AuditBus) / detach()
    # 订阅审计总线：事件 → span event/metric；EXPERT_* / VERIFIER_VERDICT 建立父子 span 语义
OtelAvailability: opentelemetry 缺失 → 装配真实 SDK 抛 AdapterError 带指引；注入 stub tracer 可测试
```
- 桥接零侵入：业务流不变，仅总线订阅；`enabled=False` 全跳过。
- 指标：`wbr.reviews.total`、`wbr.violations.total`、`wbr.tokens.total`（计数器）；span 属性 = 审计 payload。

## 7. 非目标
向量数据库依赖（语义索引为内存实现）、MCP Server 端实现、OTel Collector 部署、V2.0 全部内容。

## 8. 验收标准 → 测试映射（tests/wbr/phase6/）

| 验收标准 | 测试 |
|---|---|
| 脱敏规则命中/占位符稳定/递归对象/可关闭 | `test_redactor.py` |
| 风控策略（redact/block/off × 注入风险分级） | `test_redactor.py::test_risk_policy` |
| 知识库角色隔离 + 权限门 + 检索打分确定性 + 证据采集集成 | `test_knowledge.py` |
| 语义缓存：exact 命中优先/语义命中/契约哈希不匹配不命中/阈值与统计 | `test_semantic_cache.py` |
| 反馈闭环：记录→统计→down 聚合成黄金用例→可被回归引擎执行 | `test_feedback.py` |
| MCP：权限拒绝/二阶包裹/脱敏/可见工具过滤/StdioClient 缺 SDK 指引 | `test_mcp_bridge.py` |
| OTel：总线订阅→span/指标生成、可关闭、缺依赖指引、detach 零泄漏 | `test_otel_bridge.py` |
| 全量回归（存量零新增失败 + V1.0 套件全绿）+ 核心模块覆盖率 ≥90% | PHASE6 验收报告 |
