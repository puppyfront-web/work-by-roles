"""审计轨迹：事件收集、按 trace 检索、序列化。"""
from __future__ import annotations

import threading
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr

from wbr.core.audit.models import AuditEvent, AuditEventType, RoleBehaviorRecord, TraceTree
from wbr.core.audit.store import AuditStore


class AuditTrail(BaseModel):
    """进程内审计轨迹（线程安全）。可对接 AuditBus 广播。

    不调用 attach_store 时只保留内存列表，既有调用方不受影响。
    挂上 AuditStore 之后，append 写入存储；attach_store 会把已有记录装回列表。
    """

    events: list[AuditEvent] = Field(default_factory=list)
    behaviors: list[RoleBehaviorRecord] = Field(default_factory=list)
    lock: threading.RLock = Field(
        default_factory=threading.RLock, exclude=True, repr=False,
        validation_alias="lock", serialization_alias="lock",
    )
    _store: AuditStore | None = PrivateAttr(default=None)

    @property
    def store(self) -> AuditStore | None:
        return self._store

    def attach_store(self, store: AuditStore) -> None:
        """绑定存储，并用存储中的现有记录替换内存事件列表。"""
        self._store = store
        self.events[:] = [record.event for record in store.query()]

    def append(
        self,
        event: AuditEvent,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        with self.lock:
            if self._store is None:
                self.events.append(event)
                return
            record = self._store.append(event, run_id=run_id, session_id=session_id)
            self.events.append(record.event)

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
