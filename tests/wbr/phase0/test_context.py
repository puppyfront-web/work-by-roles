"""TC-0-CTX-1/2：TraceID 生成与上下文传播。"""
from __future__ import annotations

import threading

from wbr.core.context import (
    current_span_id,
    get_trace_id,
    new_trace_id,
    reset_trace,
    set_trace_id,
    trace_scope,
)


def test_trace_id_format_and_uniqueness():
    ids = {new_trace_id() for _ in range(1000)}
    assert len(ids) == 1000
    one = ids.pop()
    assert one.startswith("wbr-")
    hex_part = one[len("wbr-") :]
    assert len(hex_part) == 32
    int(hex_part, 16)  # 可解析为 hex


def test_context_propagation_in_thread():
    tid = new_trace_id()
    reset_trace()
    assert get_trace_id() is None
    set_trace_id(tid)
    assert get_trace_id() == tid

    seen = {}

    def worker():
        seen["tid"] = get_trace_id()

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    # 跨线程默认不可见（contextvars 语义）
    assert seen["tid"] is None
    reset_trace()


def test_span_and_scope():
    reset_trace()
    with trace_scope(span_id="span-1") as ctx:
        assert ctx.span_id == "span-1"
        assert current_span_id() == "span-1"
    assert current_span_id() is None
    reset_trace()
