"""HITL 的 LangGraph 原生映射（SPEC-003 §1.6 / D-12）。"""
from __future__ import annotations

from typing import Any

from wbr.core.orchestration.hitl import ApprovalRequest, ApprovalState, ApprovalStateMachine


def interrupt_for_approval(request: ApprovalRequest) -> Any:
    """在节点内调用：经 langgraph interrupt 暂停图执行，等待人类裁决。

    恢复侧使用 resume_with_decision / Command(resume=...)。
    """
    try:
        from langgraph.types import interrupt
    except ImportError as e:  # pragma: no cover - 环境相关
        from wbr.core.exceptions import AdapterError

        raise AdapterError("HITL interrupt 需要 langgraph: pip install langgraph") from e
    return interrupt(request.model_dump())


def resume_command(decision: ApprovalState | str, *, decided_by: str | None = None, comment: str | None = None) -> Any:
    try:
        from langgraph.types import Command
    except ImportError as e:  # pragma: no cover
        from wbr.core.exceptions import AdapterError

        raise AdapterError("HITL resume 需要 langgraph: pip install langgraph") from e
    value = decision.value if isinstance(decision, ApprovalState) else str(decision)
    ApprovalState(value)  # 校验合法裁决值
    return Command(resume={"decision": value, "decided_by": decided_by, "comment": comment})


def apply_decision(state_machine: ApprovalStateMachine, request_id: str, resume_payload: dict) -> ApprovalRequest:
    """把 interrupt 恢复载荷落回 Core 审批状态机。"""
    from wbr.core.exceptions import OrchestrationError

    raw = (resume_payload or {}).get("decision")
    try:
        decision = ApprovalState(raw)
    except ValueError as e:
        raise OrchestrationError(f"未知审批裁决: {raw!r}") from e
    return state_machine.decide(
        request_id, decision,
        decided_by=resume_payload.get("decided_by"),
        comment=resume_payload.get("comment"),
    )
