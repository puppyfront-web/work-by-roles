"""基础审计模型（SPEC-002 §4）：强类型事件 + 角色行为记录 + Trace 链路。"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.canonical import digest_of_text


class AuditEventType(str, Enum):
    SESSION_STARTED = "session_started"
    CONTRACT_COMPILED = "contract_compiled"
    EXPERT_STARTED = "expert_started"
    EXPERT_COMPLETED = "expert_completed"
    EXPERT_FAILED = "expert_failed"
    SCHEMA_VIOLATION = "schema_violation"
    FORBIDDEN_VIOLATION = "forbidden_violation"
    VERIFIER_VERDICT = "verifier_verdict"
    REVIEW_COMPLETED = "review_completed"
    MEMORY_ACCESS = "memory_access"
    TOOL_CALL = "tool_call"
    TOKEN_RECORD = "token_record"
    INTENT_REASONING = "intent_reasoning"
    LOOP_STEP = "loop_step"


class AuditEvent(BaseModel):
    """强类型审计事件（区别于 audit_bus 的通用事件）。"""

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    event_type: AuditEventType
    trace_id: str
    ts: float = Field(default_factory=time.time)
    role_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_bus_event(self):
        """转换为阶段0 审计总线的通用事件。"""
        from wbr.core.audit_bus import AuditEvent as BusEvent

        return BusEvent(
            event_type=self.event_type.value,
            trace_id=self.trace_id,
            payload={"role_id": self.role_id, **self.payload},
        )


class RoleBehaviorRecord(BaseModel):
    """角色行为记录：全文以摘要形式留存，原文外置（隐私与体积控制）。"""

    role_id: str
    action: str
    trace_id: str
    input_digest: str = ""
    output_digest: str = ""
    violations: list[str] = Field(default_factory=list)
    ts: float = Field(default_factory=time.time)

    @classmethod
    def from_texts(
        cls,
        *,
        role_id: str,
        action: str,
        trace_id: str,
        input_text: str = "",
        output_text: str = "",
        violations: list[str] | None = None,
    ) -> RoleBehaviorRecord:
        return cls(
            role_id=role_id,
            action=action,
            trace_id=trace_id,
            input_digest=digest_of_text(input_text),
            output_digest=digest_of_text(output_text),
            violations=violations or [],
        )


class TraceNode(BaseModel):
    """Trace 链路节点：一个事件在链路中的投影。"""

    event_type: AuditEventType
    ts: float
    role_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class TraceTree(BaseModel):
    """按 trace_id 聚合的事件链路。"""

    trace_id: str
    nodes: list[TraceNode] = Field(default_factory=list)

    @classmethod
    def from_events(cls, events: list[AuditEvent]) -> dict[str, TraceTree]:
        trees: dict[str, TraceTree] = {}
        for e in sorted(events, key=lambda x: x.ts):
            tree = trees.setdefault(e.trace_id, cls(trace_id=e.trace_id))
            tree.nodes.append(
                TraceNode(event_type=e.event_type, ts=e.ts, role_id=e.role_id, payload=e.payload)
            )
        return trees
