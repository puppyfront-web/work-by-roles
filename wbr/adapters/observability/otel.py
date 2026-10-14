"""OpenTelemetry 可观测桥（V1.x F6 / SPEC-007 §6）。

零侵入：订阅 AuditBus，把审计事件投影为 OTel span/metric；业务流永不阻塞。
真实 OTel SDK 可选装配（with_sdk），测试可注入 StubTracer。
"""
from __future__ import annotations

from typing import Any

from wbr.core.audit_bus import AuditBus, AuditEvent

_INSTALL_HINT = (
    "OTelBridge.with_sdk 需要 OpenTelemetry: "
    "pip install opentelemetry-api opentelemetry-sdk"
)

# 事件类型 → 指标增量
_TOKEN_EVENTS = {"token_record"}
_VIOLATION_EVENTS = {"schema_violation", "forbidden_violation"}
_REVIEW_EVENTS = {"review_completed", "session_started"}


class OTelBridge:
    """审计总线 → OTel 桥。enabled=False 全跳过（规则6）。"""

    def __init__(self, *, tracer: Any = None, meter: Any = None, enabled: bool = True) -> None:
        self.enabled = enabled
        self._tracer = tracer
        self._meter = meter
        self._bus: AuditBus | None = None
        self._token: int | None = None
        self._spans_open = 0

    @classmethod
    def with_sdk(cls, *, service_name: str = "work-by-roles", enabled: bool = True) -> "OTelBridge":
        """用真实 OpenTelemetry SDK 装配（trace + 简单计数指标）。"""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,
                ConsoleSpanExporter,
            )
        except ImportError as e:  # pragma: no cover - 环境相关
            from wbr.core.exceptions import AdapterError

            raise AdapterError(_INSTALL_HINT) from e
        provider = TracerProvider(resource=None)
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))  # 默认控制台导出，可替换
        trace.set_tracer_provider(provider)
        tracer = provider.get_tracer(service_name)
        meter_provider = MeterProvider()
        meter = meter_provider.get_meter(service_name)
        return cls(tracer=tracer, meter=meter, enabled=enabled)

    # ---- 生命周期 ----
    def attach(self, bus: AuditBus) -> None:
        if not self.enabled:
            return
        self._bus = bus
        self._token = bus.subscribe(self._on_event)

    def detach(self) -> None:
        if self._bus is not None and self._token is not None:
            self._bus.unsubscribe(self._token)
        self._bus = None
        self._token = None

    # ---- 事件处理（异常自吞，绝不反噬总线） ----
    def _on_event(self, event: AuditEvent) -> None:
        try:
            self._record_span(event)
            self._record_metric(event)
        except Exception:  # noqa: BLE001 - 可观测层零侵入
            pass

    def _record_span(self, event: AuditEvent) -> None:
        if self._tracer is None:
            return
        if hasattr(self._tracer, "start_span"):
            span = self._tracer.start_span(f"wbr.{event.event_type}")
            attrs = {"trace_id": event.trace_id or "", "event_id": event.event_id}
            attrs.update({k: v for k, v in event.payload.items() if isinstance(v, (str, int, float, bool))})
            for k, v in attrs.items():
                try:
                    span.set_attribute(k, v)
                except Exception:  # noqa: BLE001
                    pass
            try:
                span.end()
            except Exception:  # noqa: BLE001
                pass

    def _record_metric(self, event: AuditEvent) -> None:
        meter = self._meter or (self._tracer if hasattr(self._tracer, "add") else None)
        payload = event.payload or {}
        deltas: list[tuple[str, int]] = []
        if event.event_type in _REVIEW_EVENTS:
            deltas.append(("wbr.reviews.total", 1))
        if event.event_type in _VIOLATION_EVENTS:
            deltas.append(("wbr.violations.total", 1))
        if event.event_type in _TOKEN_EVENTS:
            deltas.append((
                "wbr.tokens.total",
                int(payload.get("prompt_tokens", 0)) + int(payload.get("completion_tokens", 0)),
            ))
        for name, delta in deltas:
            if meter is not None and hasattr(meter, "add"):
                meter.add(name, delta)
