"""全局 TraceID 与执行上下文（SPEC-001 §2.3）。

基于 contextvars：同协程/同线程内可见，跨线程需显式传递（编排层负责透传）。
"""
from __future__ import annotations

import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

_trace_id_var: ContextVar[str | None] = ContextVar("wbr_trace_id", default=None)
_span_id_var: ContextVar[str | None] = ContextVar("wbr_span_id", default=None)


def new_trace_id() -> str:
    """生成全局唯一 TraceID：`wbr-` + 32 位 hex。"""
    return f"wbr-{secrets.token_hex(16)}"


def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)


def get_trace_id() -> str | None:
    return _trace_id_var.get()


def set_span_id(span_id: str | None) -> None:
    _span_id_var.set(span_id)


def current_span_id() -> str | None:
    return _span_id_var.get()


def reset_trace() -> None:
    _trace_id_var.set(None)
    _span_id_var.set(None)


@dataclass(frozen=True)
class TraceContext:
    """只读上下文快照，用于跨线程/跨边界显式传递。"""

    trace_id: str | None
    span_id: str | None = None


def current_context() -> TraceContext:
    return TraceContext(trace_id=_trace_id_var.get(), span_id=_span_id_var.get())


def apply_context(ctx: TraceContext) -> None:
    """在当前执行单元恢复上下文（线程 worker 入口调用）。"""
    _trace_id_var.set(ctx.trace_id)
    _span_id_var.set(ctx.span_id)


@contextmanager
def trace_scope(span_id: str, trace_id: str | None = None) -> Iterator[TraceContext]:
    """临时进入一个 span 作用域，退出自动还原。"""
    token_t = None
    if trace_id is not None:
        token_t = _trace_id_var.set(trace_id)
    token_s = _span_id_var.set(span_id)
    try:
        yield TraceContext(trace_id=trace_id or _trace_id_var.get(), span_id=span_id)
    finally:
        _span_id_var.reset(token_s)
        if token_t is not None:
            _trace_id_var.reset(token_t)
