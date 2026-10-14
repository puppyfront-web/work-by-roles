"""原生会审 Graph 生成器（SPEC-003 §1.7）。

一键生成 Coordinator → 专家并行 → Verifier 的 LangGraph StateGraph，
节点内部复用 Core 契约编译 / Schema 校验 / 禁区检测组件。
"""
from __future__ import annotations

from typing import Any, TypedDict

from wbr.adapters.langgraph.base import require_langgraph
from wbr.adapters.langgraph.state import WBR_META_KEY
from wbr.core.audit.trail import AuditTrail
from wbr.core.contract.compiler import ContractCompiler
from wbr.core.contract.models import RoleContract
from wbr.core.orchestration.invoker import ModelInvoker, parse_json_output
from wbr.core.schema.validator import validate as schema_validate

_CONCLUSION_KEY = "conclusion"


class ReviewGraphState(TypedDict, total=False):
    question: str
    plan: dict
    expert_outputs: list
    verdict: dict
    disagreements: list
    final_answer: str
    wbr__meta: dict


def build_review_graph(
    *,
    coordinator: RoleContract,
    experts: list[RoleContract],
    verifier: RoleContract,
    invoker: ModelInvoker,
    audit: AuditTrail | None = None,
    checkpointer: Any | None = None,
):
    """生成原生会审 CompiledStateGraph。invoke({"question": ...}) 即可运行。"""
    require_langgraph()
    from langgraph.graph import END, START, StateGraph

    compiler = ContractCompiler()

    def _trace_of(state: dict | None) -> str | None:
        if not isinstance(state, dict):
            return None
        meta = state.get(WBR_META_KEY)
        return meta.get("trace_id") if isinstance(meta, dict) else None

    def _run_llm(contract: RoleContract, user_input: str, state: dict) -> dict:
        compiled = compiler.compile(contract, user_input)
        from wbr.core.orchestration.invoker import ModelRequest

        resp = invoker.invoke(
            ModelRequest(role_contract=contract, compiled_prompt=compiled,
                         trace_id=_trace_of(state) or "")
        )
        if audit is not None:
            from wbr.core.audit.models import AuditEvent, AuditEventType

            audit.append(AuditEvent(event_type=AuditEventType.CONTRACT_COMPILED,
                                    trace_id=_trace_of(state) or "no-trace",
                                    role_id=contract.role_id,
                                    payload={"contract_hash": contract.content_hash[:16]}))
        output = parse_json_output(resp.text)
        errs = schema_validate(output, contract.output_spec.schema_) if contract.output_spec.schema_ else []
        if errs and contract.output_spec.strict:
            raise ValueError(
                f"[wbr] {contract.role_id} 输出 Schema 校验失败: {errs[0].path} {errs[0].message}"
            )
        return output

    def coordinator_node(state: dict) -> dict:
        plan = _run_llm(coordinator, state["question"], state)
        return {"plan": plan}

    def make_expert_node(contract: RoleContract):
        def expert_node(state: dict) -> dict:
            plan = state.get("plan") or {}
            sub_question = state["question"]
            for a in plan.get("assignments", []):
                if a.get("expert_role_id") == contract.role_id:
                    sub_question = a.get("sub_question") or sub_question
                    break
            output = _run_llm(contract, sub_question, state)
            outputs = list(state.get("expert_outputs") or [])
            outputs.append({"role_id": contract.role_id, "sub_question": sub_question, "output": output})
            return {"expert_outputs": outputs}

        return expert_node

    def verifier_node(state: dict) -> dict:
        import json as _json

        summary = _json.dumps({
            "question": state["question"],
            "plan": state.get("plan"),
            "expert_outputs": state.get("expert_outputs") or [],
        }, ensure_ascii=False)
        verdict = _run_llm(verifier, summary, state)
        return {"verdict": verdict}

    def finalize_node(state: dict) -> dict:
        outputs = state.get("expert_outputs") or []
        verdict = state.get("verdict") or {}
        # 分歧检测（留存不仲裁）
        groups: dict[str, list[dict]] = {}
        for o in outputs:
            groups.setdefault(o.get("sub_question", ""), []).append(o)
        disagreements = []
        for topic, group in sorted(groups.items()):
            positions = [
                {"role_id": g["role_id"], _CONCLUSION_KEY: g["output"].get(_CONCLUSION_KEY)}
                for g in group if isinstance(g.get("output"), dict) and g["output"].get(_CONCLUSION_KEY) is not None
            ]
            if len({str(p[_CONCLUSION_KEY]) for p in positions}) > 1:
                disagreements.append({
                    "between": sorted(p["role_id"] for p in positions),
                    "topic": topic,
                    "positions": positions,
                })
        if verdict.get("passed"):
            answer = verdict.get("final_answer") or "\n".join(
                f"{o['role_id']}: {o['output'].get(_CONCLUSION_KEY, '')}" for o in outputs
            )
        else:
            answer = f"复核未通过：{verdict.get('comments', '')}"
        return {"disagreements": disagreements, "final_answer": answer}

    g = StateGraph(ReviewGraphState)
    g.add_node("coordinator", coordinator_node)
    for c in sorted(experts, key=lambda x: x.role_id):
        g.add_node(f"expert_{c.role_id}", make_expert_node(c))
    g.add_node("verifier", verifier_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "coordinator")
    g.add_edge("coordinator", "verifier" if not experts else f"expert_{sorted(experts, key=lambda x: x.role_id)[0].role_id}")
    ordered = sorted(experts, key=lambda x: x.role_id)
    for i, c in enumerate(ordered):
        nxt = f"expert_{ordered[i + 1].role_id}" if i + 1 < len(ordered) else "verifier"
        g.add_edge(f"expert_{c.role_id}", nxt)
    g.add_edge("verifier", "finalize")
    g.add_edge("finalize", END)

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()
