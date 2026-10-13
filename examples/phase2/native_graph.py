"""阶段2 示例 B：全新项目「原生会审 Graph」一键生成。

运行：.venv/bin/python examples/phase2/native_graph.py

演示：build_review_graph 一键生成 Coordinator → 专家并行 → Verifier 的
LangGraph 原生图，分歧留存 + checkpointer 断点续跑（interrupt 审批）。
"""
from __future__ import annotations

import sys

from wbr.adapters.langgraph import build_review_graph
from wbr.adapters.langgraph.hitl import resume_command
from wbr.core.audit.trail import AuditTrail
from wbr.core.contract import (
    EvidenceSpec,
    ForbiddenRule,
    OutputSpec,
    ReviewCriteria,
    ReviewDimension,
    RoleContract,
    RoleIdentity,
    RoleType,
    Sop,
    SopStep,
    TokenQuota,
)
from wbr.core.orchestration import ScriptedInvoker


def contract(role_id: str, name: str, rt: RoleType, **kw) -> RoleContract:
    return RoleContract.build(
        identity=RoleIdentity(role_id=role_id, name=name, role_type=rt),
        sop=Sop(steps=[SopStep(step_id="work", title="执行", instruction="按契约完成任务")]),
        output_spec=OutputSpec(schema=kw.get("schema"), strict=True),
        evidence_spec=EvidenceSpec(required=False),
        forbidden=ForbiddenRule(),
        token_quota=TokenQuota(),
        review_criteria=kw.get("criteria"),
    )


PLAN_SCHEMA = {
    "type": "object", "required": ["assignments"],
    "properties": {"assignments": {"type": "array", "items": {
        "type": "object", "required": ["expert_role_id", "sub_question"],
        "properties": {"expert_role_id": {"type": "string"}, "sub_question": {"type": "string"}},
    }}},
}
EXPERT_SCHEMA = {
    "type": "object", "required": ["conclusion", "confidence"],
    "properties": {"conclusion": {"type": "string"}, "confidence": {"type": "number"}},
}
VERDICT_SCHEMA = {
    "type": "object", "required": ["passed", "scores", "comments"],
    "properties": {"passed": {"type": "boolean"}, "scores": {"type": "object"},
                   "comments": {"type": "string"}, "final_answer": {"type": "string"}},
}


def main() -> int:
    scripts = {
        "coordinator": {"assignments": [
            {"expert_role_id": "perf_expert", "sub_question": "缓存方案对性能的影响"},
            {"expert_role_id": "cost_expert", "sub_question": "缓存方案对性能的影响"},
        ]},
        "perf_expert": {"conclusion": "引入多级缓存可降低 P99 延迟 40%", "confidence": 0.9},
        "cost_expert": {"conclusion": "多级缓存成本过高，建议单级缓存", "confidence": 0.7},
        "verifier": {"passed": True, "scores": {"completeness": 0.8, "accuracy": 0.75},
                     "comments": "性能与成本专家立场分歧，均已留存",
                     "final_answer": "建议单级缓存起步，预留多级扩展；分歧详见 disagreements"},
    }
    audit = AuditTrail()
    graph = build_review_graph(
        coordinator=contract("coordinator", "协调者", RoleType.COORDINATOR, schema=PLAN_SCHEMA),
        experts=[
            contract("perf_expert", "性能专家", RoleType.EXPERT, schema=EXPERT_SCHEMA),
            contract("cost_expert", "成本专家", RoleType.EXPERT, schema=EXPERT_SCHEMA),
        ],
        verifier=contract("verifier", "复核者", RoleType.VERIFIER, schema=VERDICT_SCHEMA,
                          criteria=ReviewCriteria(dimensions=[
                              ReviewDimension(name="completeness", weight=0.5, pass_threshold=0.6),
                              ReviewDimension(name="accuracy", weight=0.5, pass_threshold=0.6),
                          ], overall_pass_threshold=0.6)),
        invoker=ScriptedInvoker(scripts),
        audit=audit,
    )
    result = graph.invoke({"question": "是否为订单系统引入多级缓存？"})
    print("[B1] 原生会审图运行完成")
    print("    final_answer:", result["final_answer"])
    print("    分歧留存:", [(d["between"], d["topic"]) for d in result["disagreements"]])
    print("    审计事件数:", len(audit.events))
    assert result["disagreements"], "分歧应被留存"

    # HITL interrupt 演示（checkpointer 断点续跑）
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    class GateState(dict):
        pass

    import typing

    class GS(typing.TypedDict, total=False):
        action: str
        approval: dict

    sg = StateGraph(GS)

    def gate(state: GS) -> dict:
        approval = interrupt({"action": state["action"], "need": "human-approval"})
        return {"approval": approval}

    sg.add_node("gate", gate)
    sg.add_edge(START, "gate")
    sg.add_edge("gate", END)

    from wbr.adapters.langgraph import WBRGuard

    from wbr.core.contract import OutputSpec as OS, RoleContract as RC

    dummy = RC.build(
        identity=RoleIdentity(role_id="ops_actor", name="运维执行者", role_type=RoleType.EXPERT),
        sop=Sop(steps=[SopStep(step_id="x", title="X", instruction="x")]),
        output_spec=OS(schema={"type": "object"}, strict=False),
    )
    guarded = WBRGuard(output_keys={}, audit=audit).wrap(sg.compile(checkpointer=MemorySaver()))
    cfg = {"configurable": {"thread_id": "ops-1"}}
    paused = guarded.invoke({"action": "drop_legacy_cache"}, cfg)
    assert "__interrupt__" in paused, "应被 interrupt 暂停"
    resumed = guarded.invoke(resume_command(decision="approved", decided_by="ops"), cfg)  # type: ignore[arg-type]
    print("[B2] HITL 断点续跑: interrupted ->", resumed["approval"]["decision"])
    print("\n阶段2 示例 B（原生会审 Graph）通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
