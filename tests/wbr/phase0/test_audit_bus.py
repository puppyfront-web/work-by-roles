"""TC-0-BUS-1/2/3：审计事件总线：不阻塞、溢出计数、广播。"""
from __future__ import annotations

import threading
import time

from wbr.core.audit_bus import AuditBus, AuditEvent, default_bus


def _evt(i=0):
    return AuditEvent(event_type="TEST", trace_id=f"wbr-{i}", payload={"i": i})


def test_subscriber_exception_does_not_block_publish(clean_bus):
    bus = AuditBus(max_queue=100)
    errors = []

    def bad(_evt):
        raise RuntimeError("subscriber bug")

    got = []
    bus.subscribe(bad, on_error=errors.append)
    bus.subscribe(got.append)
    for i in range(5):
        bus.publish_safe(_evt(i))
    bus.flush(timeout=2.0)
    assert len(got) == 5
    assert len(errors) == 5  # 异常被捕获上报，不影响发布方


def test_overflow_drops_and_counts(clean_bus):
    bus = AuditBus(max_queue=4, sync_dispatch=False)
    gate = threading.Event()
    received = []

    def slow(evt):
        gate.wait()
        received.append(evt)

    bus.subscribe(slow)
    for i in range(50):
        bus.publish_safe(_evt(i))
    stats_mid = bus.stats()
    assert stats_mid["dropped"] > 0  # 队列打满产生丢弃
    gate.set()
    bus.flush(timeout=2.0)
    assert bus.stats()["published"] == 50  # 发布方始终成功
    assert len(received) < 50


def test_broadcast_ordered_to_all_subscribers(clean_bus):
    bus = AuditBus(max_queue=1000)
    a, b = [], []
    bus.subscribe(a.append)
    bus.subscribe(b.append)
    for i in range(10):
        bus.publish_safe(_evt(i))
    bus.flush(timeout=2.0)
    assert [e.payload["i"] for e in a] == list(range(10))
    assert [e.payload["i"] for e in b] == list(range(10))


def test_default_bus_singleton(clean_bus):
    assert default_bus() is default_bus()
    default_bus().publish_safe(_evt())
    assert default_bus().stats()["published"] >= 1


def test_sync_dispatch_mode():
    bus = AuditBus(sync_dispatch=True)
    got = []
    bus.subscribe(got.append)
    bus.publish_safe(_evt(7))
    assert len(got) == 1  # 同步模式立即派发
