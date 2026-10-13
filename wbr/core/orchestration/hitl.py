"""HITL 审批状态机（框架无关，SPEC-000 D-12）。LangGraph 映射在 Adapter 层。"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.exceptions import OrchestrationError


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


# 合法迁移表
_TRANSITIONS: dict[ApprovalState, set[ApprovalState]] = {
    ApprovalState.PENDING: {ApprovalState.APPROVED, ApprovalState.REJECTED, ApprovalState.ESCALATED},
    ApprovalState.APPROVED: set(),
    ApprovalState.REJECTED: set(),
    ApprovalState.ESCALATED: set(),
}


class ApprovalRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    question: str
    role_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = ""
    state: ApprovalState = ApprovalState.PENDING
    decided_by: str | None = None
    comment: str | None = None
    created_at: float = Field(default_factory=time.time)
    decided_at: float | None = None


class ApprovalStateMachine:
    """审批状态机：管理多个审批请求的生命周期。"""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    def create(
        self, question: str, *, role_id: str | None = None, payload: dict | None = None, trace_id: str = ""
    ) -> ApprovalRequest:
        req = ApprovalRequest(question=question, role_id=role_id, payload=payload or {}, trace_id=trace_id)
        self._requests[req.request_id] = req
        return req

    def get(self, request_id: str) -> ApprovalRequest:
        if request_id not in self._requests:
            raise OrchestrationError(f"审批请求不存在: {request_id}", code="E6002")
        return self._requests[request_id]

    def decide(
        self, request_id: str, decision: ApprovalState, *, decided_by: str | None = None, comment: str | None = None
    ) -> ApprovalRequest:
        if decision not in (ApprovalState.APPROVED, ApprovalState.REJECTED, ApprovalState.ESCALATED):
            raise OrchestrationError(f"非法裁决值: {decision}", code="E6003")
        req = self.get(request_id)
        if decision not in _TRANSITIONS[req.state]:
            raise OrchestrationError(
                f"非法状态迁移: {req.state.value} → {decision.value}", code="E6004",
                details={"request_id": request_id},
            )
        req.state = decision
        req.decided_by = decided_by
        req.comment = comment
        req.decided_at = time.time()
        return req

    def is_approved(self, request_id: str) -> bool:
        return self.get(request_id).state == ApprovalState.APPROVED

    def pending(self) -> list[ApprovalRequest]:
        return [r for r in self._requests.values() if r.state == ApprovalState.PENDING]
