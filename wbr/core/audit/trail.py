"""审计轨迹：事件收集、按 trace 检索、序列化。"""
from __future__ import annotations

import threading
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.audit.models import AuditEvent, AuditEventType, RoleBehaviorRecord, TraceTree


class AuditTrail(BaseModel):
    """进程内审计轨迹（线程安全）。可对接 AuditBus 广播。"""

    events: list[AuditEvent] = Field(default_factory=list)
    behaviors: list[RoleBehaviorRecord] = Field(default_factory=list)
    lock: threading.RLock = Field(
        default_factory=threading.RLock, exclude=True, repr=False,
        validation_alias="lock", serialization_alias="lock",
    )

    def append(self, event: AuditEvent) -> None:
        with self.lock:
            self.events.append(event)

    def append_behavior(self, record: RoleBehaviorRecord) -> None:
        with self.lock:
            self.behaviors.append(record)

    def events_for(self, trace_id: str) -> list[AuditEvent]:
        return [e for e in self.events if e.trace_id == trace_id]

    def event_types_for(self, trace_id: str) -> set[AuditEventType]:
        return {e.event_type for e in self.events_for(trace_id)}

    def tree(self, trace_id: str) -> TraceTree:
        tree = TraceTree.from_events(self.events_for(trace_id)).get(trace_id)
        if tree is None:
            tree = TraceTree(trace_id=trace_id)
        return tree

    def to_json(self) -> str:
        return self.model_dump_json()

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
