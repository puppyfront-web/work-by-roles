"""OTel 测试桩（替代真实 SDK，供注入使用）。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StubSpan:
    name: str
    attributes: dict = field(default_factory=dict)
    ended: bool = False

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def end(self):
        self.ended = True


class StubTracer:
    """记录 span/metric 的测试桩。"""

    def __init__(self) -> None:
        self.spans: list[StubSpan] = []
        self.metrics: dict[str, float] = {}

    def start_span(self, name: str) -> StubSpan:
        span = StubSpan(name=name)
        self.spans.append(span)
        return span

    def add(self, name: str, delta: float) -> None:
        self.metrics[name] = self.metrics.get(name, 0) + delta
