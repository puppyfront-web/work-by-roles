# 存量 LangGraph 项目接入指南

> 承诺：任意已有 LangGraph 项目 **3 行代码**接入本系统的治理能力，不破坏原有业务逻辑。

## 方式 A：插件式接入（WBRGuard 包装）

适用于：已有编译完成的图（`graph = your_graph.compile()`），想获得输入防注入、输出 Schema/禁区拦截、审计、Token 计量。

```python
from wbr.adapters.langgraph import WBRGuard
from wbr.core.audit import AuditTrail

# 你已有的图与 State 完全不动
your_graph = build_your_graph().compile(checkpointer=MemorySaver())
contract = load_contract("db_analyst")          # 绑定到输出键的契约
trail = AuditTrail()

guard = WBRGuard(                                # 第 1 行
    output_keys={"answer": contract},            #   声明要治理的输出键
    audit=trail,                                 #   全链路审计（可选）
    security="record",                           #   注入处置: record|block|off（默认 record）
    schema_validation="record",                  #   Schema 处置: record|block|off
    forbidden_check="record",                    #   禁区处置: record|block|off
)
graph = guard.wrap(your_graph)                   # 第 2 行
result = graph.invoke({"question": "..."})       # 第 3 行（原 config/checkpointer 原样透传）
```

接入后发生什么：
- 用户 State 的业务键**原值不变**（测试保证：stub 节点调用次数与入参逐项断言）；
- `result["wbr__meta"]` 注入 `{trace_id, input_scan, violations}`；
- 高危注入在 `security="block"` 时于图执行**之前**阻断（抛 `SecurityViolationError`）；
- 违规输出按 record（仅记录）/ block（置 None）处置，并写入审计事件；
- MemorySaver / interrupt / `Command(resume=...)` 全部兼容（恢复路径自动透传）。

节点级加固（可选）：`@guard.guard_node(contract)` 装饰单个节点函数，strict 契约下违规在节点内即失败。

## 方式 B：原生会审 Graph（一键生成）

适用于：新项目想直接获得 Coordinator → 专家并行 → Verifier 的完整会审图。

```python
from wbr.adapters.langgraph import build_review_graph
from wbr.templates.registry import load_team_spec

spec = load_team_spec("arch_review_team")
graph = build_review_graph(
    coordinator=spec.coordinator,
    experts=spec.experts,
    verifier=spec.verifier,
    invoker=your_invoker,          # ModelInvoker 协议（同 SDK）
    audit=AuditTrail(),
    checkpointer=MemorySaver(),    # 可选
)
result = graph.invoke({"question": "评审这个方案"})
# result["final_answer"] / result["disagreements"] / result["verdict"]
```

## HITL：人工审批断点

```python
from wbr.adapters.langgraph import interrupt_for_approval, resume_command
from wbr.core.orchestration.hitl import ApprovalStateMachine, ApprovalState

sm = ApprovalStateMachine()

def human_gate_node(state):
    req = sm.create("是否执行高危变更?", role_id="ops", trace_id=state["wbr__meta"]["trace_id"])
    payload = interrupt_for_approval(req)          # 图在此暂停（langgraph interrupt）
    apply_decision(sm, req.request_id, payload)    # 恢复后落回状态机
    return {"approval": payload}

# 恢复执行：
graph.invoke(Command(resume={"decision": "approved", "decided_by": "ops"}), config)
# 或使用辅助构造：resume_command(ApprovalState.APPROVED, decided_by="ops")
```

## 记忆持久化（Redis / 内存）

```python
from wbr.adapters.storage import RedisStorageBackend
from wbr.adapters.storage.store import persistent_memory_hub

backend = RedisStorageBackend(redis.Redis.from_url("redis://localhost:6379/0"))
memory = persistent_memory_hub(backend, audit=trail)
# 角色记忆键: wbr:{layer}:{scope}:{key}，四层隔离语义与进程内实现完全一致
```

## Token 治理接线

```python
from wbr.core.token import TokenMeter, TokenBudget, BudgetPolicy

meter = TokenMeter()
budget = TokenBudget(BudgetPolicy(max_total_tokens=200_000, on_exceed="degrade"), meter)
guard = WBRGuard(..., token_meter=meter)   # 图级计量；预算检查可在自定义节点内调用 budget.check(role_id)
```

## 真实模型接入

`ModelInvoker` 协议是唯一接缝。示例：把 LangChain 聊天模型包成 Invoker：

```python
from wbr.core.orchestration import ModelRequest, ModelResponse, TokenUsage
from wbr.core.orchestration.invoker import parse_json_output

class LangChainInvoker:
    def __init__(self, chat_model):
        self._model = chat_model
    def invoke(self, request: ModelRequest) -> ModelResponse:
        from langchain_core.messages import HumanMessage, SystemMessage
        msgs = [SystemMessage(content=request.compiled_prompt.system_prompt),
                HumanMessage(content=request.compiled_prompt.user_block)]
        resp = self._model.invoke(msgs)
        return ModelResponse(text=resp.content, usage=TokenUsage(prompt_tokens=0, completion_tokens=0))
```

可运行示例：[examples/phase2/legacy_plugin_integration.py](../examples/phase2/legacy_plugin_integration.py)、
[examples/phase2/native_graph.py](../examples/phase2/native_graph.py)。
