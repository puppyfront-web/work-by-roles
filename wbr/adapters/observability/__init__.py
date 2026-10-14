"""可观测子包公共导出（V1.x F6）。"""
from wbr.adapters.observability.otel import OTelBridge

__all__ = ["OTelBridge"]


def __getattr__(name: str):
    if name in ("StubSpan", "StubTracer"):
        from wbr.adapters.observability.stub import StubSpan, StubTracer

        return {"StubSpan": StubSpan, "StubTracer": StubTracer}[name]
    raise AttributeError(name)
