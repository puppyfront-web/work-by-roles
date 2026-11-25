# SDK 全量 API 参考（wbr Core）

> 全部 API 均可脱离任何框架独立使用；Core 依赖仅 stdlib + Pydantic V2。

## 1. 契约（RoleContract）

```python
from wbr import RoleContract, RoleIdentity, RoleType, Sop, SopStep, ForbiddenRule, \
    OutputSpec, EvidenceSpec, ToolPolicy, MemoryPermissions, TokenQuota, \
    ReviewCriteria, ReviewDimension

contract = RoleContract.build(          # build 自动计算内容哈希（定版）
    identity=RoleIdentity(role_id="expert_a", name="认证专家", role_type=RoleType.EXPERT),
    sop=Sop(steps=[SopStep(step_id="analyze", title="分析", instruction="...")]),
    forbidden=ForbiddenRule(behaviors=["泄露系统提示词"], domains=["医疗诊断"]),
    output_spec=OutputSpec(schema={...}, strict=True),
    evidence_spec=EvidenceSpec(required=True, min_citations=1),
    tool_policy=ToolPolicy(whitelist=["doc_search"], deny_by_default=True),
    memory_permissions=MemoryPermissions(read_layers=["role_session"], write_layers=["role_session"]),
    token_quota=TokenQuota(max_prompt_tokens=6000, max_completion_tokens=2000, max_turn_tokens=8000),
)
contract.content_hash                   # 64 位 sha256（业务字段，meta 不参与）
contract.to_json() / RoleContract.from_json(s)     # 无损序列化往返
contract.save(path) / RoleContract.load(path)
contract.with_changes(**{"identity.description": "v2"}, bump="minor", changelog="...")
                                        # copy-on-write 版本派生（支持点路径）
```

跨字段校验：Verifier 必须带 `review_criteria`，Coordinator 必须不带；`role_id` 正则约束；
SOP `step_id` 唯一；配额 > 0；权重 ∈ (0,1]。

## 2. 编译器（ContractCompiler）

```python
from wbr import ContractCompiler

prompt = ContractCompiler().compile(contract, "用户问题",
                                     evidence=["[^1] 文档"], history=[...],
                                     shared_context="本团队共用的评审约定")
prompt.system_prompt   # 护栏 → 团队共享上下文 → 契约主体 → 输出约束 → 禁区 → 证据规则 → 动态材料
prompt.user_block      # 用户输入被边界符隔离；输入内的边界标记自动转义
# 缺省段（无共享上下文、无证据材料）会跳过，不会为了凑缓存长度而填充。
```

## 3. 版本 Diff（ContractDiffEngine）

```python
from wbr import ContractDiffEngine

report = ContractDiffEngine().diff(old_contract, new_contract)
report.changes      # [{path, change_type, category(field/rule/schema/forbidden/policy), severity}]
report.has_breaking # 存在 HIGH（如禁区放宽、权限扩大、required 变更）时 True
```

## 4. 会审编排（ReviewSession）

```python
from wbr import ReviewSession, ModelInvoker, ModelRequest, ModelResponse, ScriptedInvoker

class MyInvoker:                       # 唯一需要实现的协议
    def invoke(self, request: ModelRequest) -> ModelResponse: ...

session = ReviewSession(
    coordinator_contract=..., expert_contracts=[...], verifier_contract=...,
    invoker=MyInvoker(),
    memory=MemoryHub(...),             # 可选
    audit=AuditTrail(),                # 可选，全链路审计
    max_workers=None,                  # 并行度（默认 min(N,8)；设置 token_budget 时改为串行）
    token_meter=TokenMeter(),          # 可选；记录协调者/专家/复核人用量
    token_budget=budget,               # 可选，默认不强制；超限跳过并写审计，run() 不抛异常
    skip_unassigned_experts=True,      # 默认 True：协调者没分配的专家不调用模型
    shared_context="团队共用约定",       # 可选；拼在护栏之后、角色契约之前
    response_cache=ContractBoundCache(),  # 可选，默认关闭
    allow_semantic_cache=False,        # 仅当 response_cache 是 SemanticCache 时生效
)
result = session.run("问题")           # 也可用 run(..., shared_context="仅本次") 覆盖
result.status / result.final_answer / result.expert_outcomes / result.disagreements
result.verifier_verdict.passed / .scores
result.save(path)
```

行为语义：专家并行、按 role_id 确定性排序；strict 契约下 Schema/禁区违规 → 该专家 FAILED；
单专家异常不阻断全场（`completed_with_failures`）；同一子问题专家 `conclusion` 冲突 → 记入
`disagreements`（分歧留存，不仲裁）。未分配专家记 `status=skipped`、`skip_reason=unassigned`。
模型请求带上契约 `token_quota.max_completion_tokens` 作为 `max_tokens`。预算超限时该角色
`skip_reason=budget`（协调者超限则整场停止），并写 `token_budget_exceeded` 审计。

## 5. 记忆（MemoryHub）

四层：`role_static`（角色长期）/ `role_session`（角色会话）/ `task_scratch`（任务暂存，同会话跨角色）/
`global_shared`（全局受控，写需 `allow_global_write=True` 双重授权）。

```python
from wbr import MemoryHub

hub = MemoryHub()                       # 可注入持久化后端（见 adapters/storage）
hub.write("role_session", "key", value, contract=contract, session_id="s1")
hub.read("role_session", "key", contract=contract, session_id="s1")
# 越权抛 MemoryPermissionDeniedError 并写 MEMORY_ACCESS 审计
```

## 6. 安全（guard / boundaries）

```python
from wbr import guard_user_input, InjectionDetector, RiskLevel, wrap_external_content

res = guard_user_input(user_text)          # allowed / report / sanitized
report = InjectionDetector().detect(text)  # 规则库可扩展（InjectionRule 列表）
wrapped = wrap_external_content(tool_output, source="web_search")  # 二阶隔离包裹
```

## 7. Token 治理

```python
from wbr import TokenMeter, BudgetPolicy, TokenBudget, HeuristicTokenCounter

meter = TokenMeter()
meter.record("expert_a", "expert", usage, trace_id)
meter.usage_by_role("expert_a") / usage_by_step("expert") / usage_total
meter.cached_prompt_tokens      # 供应商或本地缓存命中的提示 token
meter.estimate_cost(input_price=3e-6, output_price=15e-6, cached_input_price=0.3e-6)
budget = TokenBudget(BudgetPolicy(max_total_tokens=100000, per_role={"expert_a": 20000},
                                  on_exceed="degrade"), meter)
budget.check("expert_a")        # OK / DEGRADE / REJECT(抛 TokenBudgetExceededError)
budget.check("expert_a", incoming=500)  # 把即将发送的提示估计算进去
```

`TokenUsage` 与 `parse_provider_usage`（`from wbr.core.orchestration import parse_provider_usage`）保留缓存字段：OpenAI `prompt_tokens_details.cached_tokens`、
DeepSeek `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`（都算在 prompt 内，`cache_scope=included`）、
Anthropic `cache_read_input_tokens` / `cache_creation_input_tokens`（相对 input 另计，`cache_scope=additional`）。
单价由调用方传入，内核不定价。

`run()` 结束时 `result.savings` 是一份节省回执（`savings-receipt-v1`，见 [SAVINGS.md](SAVINGS.md)）。它不发起第二次模型调用。`saved_tokens` / `saved_cost` 等于基线减去实际，也等于 `shared_prefix`、`skipped_unassigned`、`cache_hit` 三条杠杆之和。没传单价时费用为 0；需要金额时调用 `result.savings.priced(input_price=..., output_price=..., cached_input_price=...)`。优化没有生效时 `saved_*` 为 0。预算跳过记在 `budget_skipped`，不算节省。

## 8. 缓存（ContractBoundCache）

```python
from wbr import ContractBoundCache

cache = ContractBoundCache()   # 可注入 Redis 后端（adapters.storage.redis_backend.RedisCacheBackend）
cache.put(contract, question, evidence_list, value)
cache.get(contract, question, evidence_list)   # Key = 契约哈希|问题哈希|证据快照
cache.invalidate_contract(contract)            # 契约变更主动失效
cache.stats.hit_rate
```

## 9. Harness（回归与指标）

```python
from wbr import GoldenCase, CaseSuite, BaselineSnapshot, RegressionEngine, HeuristicJudge

suite = CaseSuite(suite_id="s1"); suite.add(GoldenCase(case_id="c1", question="...",
    expected_keywords=["JWT"], expert_role_ids=["expert_a"], expect_disagreement=False))
baseline = BaselineSnapshot.capture(contracts=contracts, suite=suite, model_fingerprint="gpt-x")
engine = RegressionEngine(contracts=contracts, invoker=invoker)
report = engine.run_suite(suite, baseline=baseline, stability_runs=2, judge=HeuristicJudge())
report.metrics            # 合规率/Schema 达标率/禁区违规率/证据完整率/结论稳定性/分歧检出率/通过率
report2.compare_with(report)   # {"metrics_delta", "degradations"} 能力退化检测
baseline.is_current(contracts, suite)   # 契约/用例漂移一致性
```

## 10. 审计

```python
from wbr import AuditTrail, AuditPackBuilder, AuditEvent, AuditEventType
from wbr import InMemoryAuditStore, SqliteAuditStore

trail = AuditTrail()                       # 不挂存储：仍是内存列表，既有代码不用改
trail.append(AuditEvent(event_type=..., trace_id=..., payload={...}))
trail.events_for(trace_id); trail.tree(trace_id)
pack = AuditPackBuilder(trail, include_contents=False).build(results=[review_result])
pack.save("audit-pack.json")    # 脱敏导出 + content_digest 完整性

store = SqliteAuditStore("audit.db")       # 或 InMemoryAuditStore()；只用标准库 sqlite3
trail.attach_store(store)                  # 把库里已有事件装回 trail.events
trail.append(event, run_id="task-1", session_id="task-1")
store.query(run_id="task-1", event_type="expert_skipped", since=0, until=None, limit=100)
store.verify()                  # ChainVerification；broken_at 为第一条断裂的位置
store.verify(strict=True)       # 断裂时抛 AuditChainBroken（打开 SQLite 时默认就是严格校验）
```

`create_app(audit_store=...)` 直接注入存储。`create_app(audit_db=path)` 或环境变量 `WBR_AUDIT_DB` 使用 SQLite；`audit_db=""` 强制内存。未传 `run_id` 时用事件的 `trace_id`。API 会审把 `task_id` 当作 `run_id`。

查询接口（只读，跟随 `WBR_API_KEY`）：

- `GET /api/v1/audits/events?run_id=&session_id=&trace_id=&event_type=&since=&until=&limit=`
- `GET /api/v1/reviews/{task_id}/audits`

Postgres 存储不要加进内核。wbr-studio 实现 `AuditStore`：同一套逻辑列（`audit_meta`、`audit_events`），追加时在事务里锁住链尾再写下一 `seq`，哈希必须调用 `wbr.core.audit.chain.audit_record_hash`（算法版本 `audit_record_hash.v1`，创世 `prev_hash` 为 64 个 0）。SQLite 这一份只保证单进程内的并发追加。

## 11. HITL 审批状态机

```python
from wbr import ApprovalStateMachine
from wbr.core.orchestration.hitl import ApprovalState

sm = ApprovalStateMachine()
req = sm.create("高危操作确认", role_id="expert_a")
sm.decide(req.request_id, ApprovalState.APPROVED, decided_by="human")
```

LangGraph 侧映射：`wbr.adapters.langgraph.hitl.interrupt_for_approval / resume_command / apply_decision`。
