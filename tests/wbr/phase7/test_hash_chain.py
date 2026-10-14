"""TC-V2-CHAIN：防篡改审计哈希链。"""
from __future__ import annotations

import json

import pytest

from wbr.core.audit.chain import HashChainAuditor, HashChainTrail
from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.trail import AuditTrail


def test_genesis_and_sequential_hashes():
    chain = HashChainAuditor()
    e1 = chain.append(AuditEvent(event_type=AuditEventType.SESSION_STARTED, trace_id="t1"))
    e2 = chain.append(AuditEvent(event_type=AuditEventType.EXPERT_STARTED, trace_id="t1"))
    assert e1.seq == 0 and e1.prev_hash == "0" * 64
    assert e2.seq == 1 and e2.prev_hash == e1.event_hash
    assert chain.verify().ok is True and chain.verify().checked == 2


def test_tamper_payload_detected_and_located():
    chain = HashChainAuditor()
    chain.append(AuditEvent(event_type=AuditEventType.SESSION_STARTED, trace_id="t1"))
    chain.append(AuditEvent(event_type=AuditEventType.TOKEN_RECORD, trace_id="t1", payload={"n": 1}))
    # 篡改第 2 个事件（模拟存储被篡改）
    chain._events[1].event.payload["n"] = 999
    v = chain.verify()
    assert v.ok is False and v.broken_at == 1


def test_deletion_and_reorder_detected():
    chain = HashChainAuditor()
    for i in range(4):
        chain.append(AuditEvent(event_type=AuditEventType.MEMORY_ACCESS, trace_id=f"t{i}"))
    # 删除中间事件（模拟）
    del chain._events[1]
    v = chain.verify()
    assert v.ok is False

    chain2 = HashChainAuditor()
    for i in range(3):
        chain2.append(AuditEvent(event_type=AuditEventType.MEMORY_ACCESS, trace_id=f"t{i}"))
    chain2._events[0], chain2._events[1] = chain2._events[1], chain2._events[0]
    assert chain2.verify().ok is False


def test_export_import_roundtrip_preserves_verification():
    chain = HashChainAuditor()
    for i in range(3):
        chain.append(AuditEvent(event_type=AuditEventType.TOKEN_RECORD, trace_id=f"t{i}",
                                payload={"n": i}))
    raw = chain.export_json()
    restored = HashChainAuditor.from_json(raw)
    assert restored.verify().ok is True
    assert len(restored.chain()) == 3
    json.loads(raw)  # 可解析


def test_chain_trail_facade_writes_both():
    trail = AuditTrail()
    ct = HashChainTrail(trail)
    ct.append(AuditEvent(event_type=AuditEventType.SESSION_STARTED, trace_id="t1"))
    assert len(trail.events) == 1          # trail 同步写入
    assert ct.verify().ok is True
    assert ct.chain()[0].event_hash


def test_verify_empty_chain():
    assert HashChainAuditor().verify().ok is True
