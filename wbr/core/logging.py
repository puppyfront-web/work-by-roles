"""基础日志架构：JSON 结构化输出 + trace_id 注入（SPEC-001 §2.6）。"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from wbr.core.config import WBRConfig
from wbr.core.context import get_trace_id

_CONFIGURED_KEY = "wbr_logging_configured"


class JsonFormatter(logging.Formatter):
    """单行 JSON 格式化：ts/level/name/trace_id/message/extra。"""

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, Any] = {
            "ts": round(record.created or time.time(), 3),
            "level": record.levelname,
            "name": record.name,
            "trace_id": getattr(record, "trace_id", None) or get_trace_id(),
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra", None)
        if extra:
            obj["extra"] = extra
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False, default=str)


class TraceFilter(logging.Filter):
    """将当前 trace_id 注入每条日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = get_trace_id()  # type: ignore[attr-defined]
        return True


class WBRAuditLogger:
    """日志门面：调用方通过 info/warning/error 记录，extra 携带结构化字段。"""

    def __init__(self, name: str, *, trace_id: str | None = None) -> None:
        self.logger = logging.getLogger(name)
        self._fixed_trace_id = trace_id
        if not any(isinstance(f, TraceFilter) for f in self.logger.filters):
            self.logger.addFilter(TraceFilter())

    def _log(self, level: int, msg: str, *args: Any, extra: dict[str, Any] | None = None) -> None:
        payload = dict(extra or {})
        if self._fixed_trace_id:
            payload.setdefault("trace_id", self._fixed_trace_id)
        self.logger.log(level, msg, *args, extra={"extra": payload})

    def debug(self, msg: str, *args: Any, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.DEBUG, msg, *args, extra=extra)

    def info(self, msg: str, *args: Any, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.INFO, msg, *args, extra=extra)

    def warning(self, msg: str, *args: Any, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.WARNING, msg, *args, extra=extra)

    def error(self, msg: str, *args: Any, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.ERROR, msg, *args, extra=extra)


def get_logger(name: str, *, trace_id: str | None = None) -> WBRAuditLogger:
    return WBRAuditLogger(name, trace_id=trace_id)


def setup_logging(config: WBRConfig) -> None:
    """幂等初始化 root handler（重复调用不叠加 handler）。"""
    root = logging.getLogger()
    if getattr(root, _CONFIGURED_KEY, False):
        root.setLevel(config.log_level.upper())
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TraceFilter())
    root.addHandler(handler)
    root.setLevel(config.log_level.upper())
    setattr(root, _CONFIGURED_KEY, True)


def reset_logging() -> None:
    """撤销 setup_logging 添加的 handler（测试隔离用）。"""
    root = logging.getLogger()
    if getattr(root, _CONFIGURED_KEY, False):
        for h in list(root.handlers):
            root.removeHandler(h)
        setattr(root, _CONFIGURED_KEY, False)
