"""防篡改审计哈希链（V2.0 E1 / SPEC-008 §1）。

event_hash = sha256(canonical_json(prev_hash|seq|事件全文))，创世 prev_hash=0*64。
与 AuditTrail 并存（R24）：HashChainTrail 门面同写两处，存量零影响。
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from wbr.core.audit.models import AuditEvent
from wbr.core.canonical import canonical_json, sha256_hex

GENESIS = "0" * 64


class ChainedEvent(BaseModel):
    seq: int
    prev_hash: str
    event_hash: str
    event: AuditEvent


class ChainVerification(BaseModel):
    ok: bool
    broken_at: int | None = None
    checked: int = 0


def _hash(prev_hash: str, seq: int, event: AuditEvent) -> str:
    payload = canonical_json({
        "prev_hash": prev_hash,
        "seq": seq,
        "event": event.model_dump(mode="json"),
    })
    return sha256_hex(payload)


class HashChainAuditor:
    """进程内哈希链审计器：追加即定版，历史篡改可检出并定位。"""

    def __init__(self) -> None:
        self._events: list[ChainedEvent] = []

    def append(self, event: AuditEvent) -> ChainedEvent:
        prev_hash = self._events[-1].event_hash if self._events else GENESIS
        seq = len(self._events)
        chained = ChainedEvent(
            seq=seq, prev_hash=prev_hash, event_hash=_hash(prev_hash, seq, event), event=event
        )
        self._events.append(chained)
        return chained

    def chain(self) -> list[ChainedEvent]:
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def verify(self) -> ChainVerification:
        prev = GENESIS
        for i, chained in enumerate(self._events):
            if chained.seq != i or chained.prev_hash != prev:
                return ChainVerification(ok=False, broken_at=i, checked=i)
            if chained.event_hash != _hash(chained.prev_hash, chained.seq, chained.event):
                return ChainVerification(ok=False, broken_at=i, checked=i + 1)
            prev = chained.event_hash
        return ChainVerification(ok=True, checked=len(self._events))

    # ---- 持久化 ----
    def export_json(self) -> str:
        return json.dumps(
            {"format_version": "1.0", "events": [e.model_dump(mode="json") for e in self._events]},
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, raw: str) -> HashChainAuditor:
        data = json.loads(raw)
        auditor = cls()
        auditor._events = [ChainedEvent.model_validate(e) for e in data["events"]]
        return auditor


class HashChainTrail:
    """门面：append 同时写入 AuditTrail 与哈希链。"""

    def __init__(self, trail: Any) -> None:
        self.trail = trail
        self.chain_auditor = HashChainAuditor()

    def append(self, event: AuditEvent) -> ChainedEvent:
        self.trail.append(event)
        return self.chain_auditor.append(event)

    def chain(self) -> list[ChainedEvent]:
        return self.chain_auditor.chain()

    def verify(self) -> ChainVerification:
        return self.chain_auditor.verify()
