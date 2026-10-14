"""TC-V1.1-OTEL：OpenTelemetry 可观测桥。"""
from __future__ import annotations

import pytest

from wbr.adapters.observability import OTelBridge
from wbr.adapters.observability.stub import StubSpan, StubTracer
from wbr.core.audit_bus import AuditBus, AuditEvent
from wbr.core.security.guard import RiskLevel


def make_bus() -> AuditBus:
    return AuditBus(sync_dispatch=True)


def test_events_become_spans():
    tracer = StubTracer()
    bus = make_bus()
    bridge = OTelBridge(tracer=tracer)
    bridge.attach(bus)
    bus.publish(AuditEvent(event_type="expert_started", trace_id="wbr-1",
                           payload={"role_id": "expert_a"}))
    bus.publish(AuditEvent(event_type="verifier_verdict", trace_id="wbr-1",
                           payload={"passed": True}))
    bridge.detach()
    names = [s.name for s in tracer.spans]
    assert "wbr.expert_started" in names and "wbr.verifier_verdict" in names
    span = next(s for s in tracer.spans if s.name == "wbr.expert_started")
    assert span.attributes["role_id"] == "expert_a"
    assert span.attributes["trace_id"] == "wbr-1"


def test_metrics_counters():
    tracer = StubTracer()
    bus = make_bus()
    bridge = OTelBridge(tracer=tracer)
    bridge.attach(bus)
    bus.publish(AuditEvent(event_type="review_completed", trace_id="t", payload={"status": "completed"}))
    bus.publish(AuditEvent(event_type="schema_violation", trace_id="t", payload={}))
    bus.publish(AuditEvent(event_type="forbidden_violation", trace_id="t", payload={}))
    bus.publish(AuditEvent(event_type="token_record", trace_id="t",
                           payload={"prompt_tokens": 10, "completion_tokens": 5}))
    bridge.detach()
    m = tracer.metrics
    assert m["wbr.reviews.total"] == 1
    assert m["wbr.violations.total"] == 2
    assert m["wbr.tokens.total"] == 15


def test_disabled_bridge_skips_everything():
    tracer = StubTracer()
    bus = make_bus()
    bridge = OTelBridge(tracer=tracer, enabled=False)
    bridge.attach(bus)
    bus.publish(AuditEvent(event_type="review_completed", trace_id="t", payload={}))
    bridge.detach()
    assert tracer.spans == [] and tracer.metrics == {}


def test_detach_stops_consuming():
    tracer = StubTracer()
    bus = make_bus()
    bridge = OTelBridge(tracer=tracer)
    bridge.attach(bus)
    bridge.detach()
    bus.publish(AuditEvent(event_type="review_completed", trace_id="t", payload={}))
    assert tracer.spans == []  # detach 后不再消费


def test_audit_bus_not_blocked_by_bridge():
    tracer = StubTracer()
    bus = make_bus()
    bridge = OTelBridge(tracer=tracer)
    bridge.attach(bus)
    # 桥内部异常不影响发布方
    bus.publish(AuditEvent(event_type="review_completed", trace_id="t", payload={"status": "ok"}))
    assert bus.stats()["published"] == 1


def test_real_sdk_assembly_gated():
    """真实 OTel SDK 装配：已安装则构建成功，未安装抛指引错误。"""
    try:
        import opentelemetry.sdk  # noqa: F401
        bridge = OTelBridge.with_sdk(service_name="wbr-test")
        assert bridge is not None
    except ImportError:
        with pytest.raises(Exception, match="opentelemetry"):
            OTelBridge.with_sdk(service_name="wbr-test")


def test_risk_level_in_attributes():
    tracer = StubTracer()
    bus = make_bus()
    bridge = OTelBridge(tracer=tracer)
    bridge.attach(bus)
    bus.publish(AuditEvent(event_type="forbidden_violation", trace_id="t",
                           payload={"detail": "x", "risk": "high"}))
    bridge.detach()
    span = tracer.spans[-1]
    assert span.attributes.get("risk") in (RiskLevel.HIGH, RiskLevel.HIGH.value, "high")
