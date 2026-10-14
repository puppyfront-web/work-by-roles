"""审计事件总线：进程内 pub/sub，绝不阻塞业务流（SPEC-001 §2.7 / D-14）。

- 有界队列 + 后台派发线程；溢出丢弃并计数（dropped）。
- 订阅者异常被捕获并上报 on_error 回调，调用方无感。
- sync_dispatch=True 时同步派发（测试/嵌入式场景）。
"""
from __future__ import annotations

import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.context import get_trace_id


class AuditEvent(BaseModel):
    """阶段0 通用审计事件；阶段1 起配套强类型事件类型枚举。"""

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    event_type: str
    trace_id: str | None = Field(default_factory=get_trace_id)
    ts: float = Field(default_factory=lambda: __import__("time").time())
    payload: dict[str, Any] = Field(default_factory=dict)


Subscriber = Callable[[AuditEvent], None]
ErrorHandler = Callable[[BaseException], None]


@dataclass
class _Subscription:
    callback: Subscriber
    on_error: ErrorHandler | None = None
    active: bool = True


class AuditBus:
    """审计事件总线。publish_safe 永不向业务方抛异常。"""

    def __init__(
        self,
        *,
        max_queue: int = 10000,
        sync_dispatch: bool = False,
    ) -> None:
        self._sync = sync_dispatch
        self._queue: queue.Queue[AuditEvent | None] = queue.Queue(maxsize=max_queue)
        self._subs: list[_Subscription] = []
        self._lock = threading.Lock()
        self._published = 0
        self._dropped = 0
        self._errors = 0
        self._worker: threading.Thread | None = None
        if not sync_dispatch:
            self._worker = threading.Thread(
                target=self._run, name="wbr-audit-bus", daemon=True
            )
            self._worker.start()

    # ---- 订阅 ----
    def subscribe(self, callback: Subscriber, *, on_error: ErrorHandler | None = None) -> int:
        with self._lock:
            self._subs.append(_Subscription(callback, on_error))
            return len(self._subs) - 1

    def unsubscribe(self, token: int) -> None:
        with self._lock:
            if 0 <= token < len(self._subs):
                self._subs[token].active = False

    # ---- 发布 ----
    def publish(self, event: AuditEvent) -> None:
        """同步 API：直接派发（队列模式则入队）。供确定性场景使用。"""
        self._published += 1
        self._dispatch(event)

    def publish_safe(self, event: AuditEvent) -> None:
        """发布事件，任何情况下不抛异常、不阻塞超过入队尝试。"""
        try:
            self._published += 1
            if self._sync:
                self._dispatch(event)
                return
            try:
                self._queue.put_nowait(event)
            except queue.Full:
                self._dropped += 1
        except Exception:
            self._errors += 1

    # ---- 内部 ----
    def _dispatch(self, event: AuditEvent) -> None:
        with self._lock:
            subs = [s for s in self._subs if s.active]
        for sub in subs:
            try:
                sub.callback(event)
            except Exception as e:
                self._errors += 1
                if sub.on_error is not None:
                    try:
                        sub.on_error(e)
                    except Exception:
                        pass

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                continue
            self._dispatch(item)

    # ---- 观测 ----
    def stats(self) -> dict[str, int]:
        return {
            "published": self._published,
            "dropped": self._dropped,
            "errors": self._errors,
            "subscribers": len([s for s in self._subs if s.active]),
        }

    def flush(self, timeout: float = 2.0) -> None:
        """等待队列中已有事件派发完成（测试辅助）。"""
        if self._sync:
            return
        deadline = __import__("time").time() + timeout
        while __import__("time").time() < deadline:
            if self._queue.empty():
                return
            __import__("time").sleep(0.01)


_default_bus: AuditBus | None = None


def default_bus() -> AuditBus:
    """全局默认总线单例（可注入替换，测试用 reset_default_bus 隔离）。"""
    global _default_bus
    if _default_bus is None:
        _default_bus = AuditBus()
    return _default_bus


def reset_default_bus() -> None:
    global _default_bus
    _default_bus = None
