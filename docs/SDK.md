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
                                     evidence=["[^1] 文档"], history=[...])
prompt.system_prompt   # 护栏头 → 契约主体 → 输出约束 → 禁区 → 证据规范（固定段序）
prompt.user_block      # 用户输入被边界符隔离；输入内的边界标记自动转义
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
    max_workers=None,                  # 并行度（默认 min(N,8)）
)
result = session.run("问题")
result.status / result.final_answer / result.expert_outcomes / result.disagreements
result.verifier_verdict.passed / .scores
result.save(path)
```

行为语义：专家并行、按 role_id 确定性排序；strict 契约下 Schema/禁区违规 → 该专家 FAILED；
单专家异常不阻断全场（`completed_with_failures`）；同一子问题专家 `conclusion` 冲突 → 记入
`disagreements`（分歧留存，不仲裁）。

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
budget = TokenBudget(BudgetPolicy(max_total_tokens=100000, per_role={"expert_a": 20000},
                                  on_exceed="degrade"), meter)
budget.check("expert_a")        # OK / DEGRADE / REJECT(抛 TokenBudgetExceededError)
```

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

trail = AuditTrail(); trail.append(AuditEvent(event_type=..., trace_id=..., payload={...}))
trail.events_for(trace_id); trail.tree(trace_id)
pack = AuditPackBuilder(trail, include_contents=False).build(results=[review_result])
pack.save("audit-pack.json")    # 脱敏导出 + content_digest 完整性
```

## 11. HITL 审批状态机

```python
from wbr import ApprovalStateMachine
from wbr.core.orchestration.hitl import ApprovalState

sm = ApprovalStateMachine()
req = sm.create("高危操作确认", role_id="expert_a")
sm.decide(req.request_id, ApprovalState.APPROVED, decided_by="human")
```

LangGraph 侧映射：`wbr.adapters.langgraph.hitl.interrupt_for_approval / resume_command / apply_decision`。
