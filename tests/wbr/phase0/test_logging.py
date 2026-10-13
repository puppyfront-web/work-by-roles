"""TC-0-LOG-1/2：JSON 日志格式与幂等初始化。"""
from __future__ import annotations

import io
import json
import logging

from wbr.core.config import WBRConfig
from wbr.core.context import new_trace_id, set_trace_id
from wbr.core.logging import JsonFormatter, get_logger, reset_logging, setup_logging


def _capture(caplog):
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    lg = get_logger("wbr.test.json")
    lg.logger.addHandler(handler)
    lg.logger.propagate = False
    try:
        yield lg, buf
    finally:
        lg.logger.removeHandler(handler)
        lg.logger.propagate = True


def test_json_single_line_with_trace(caplog):
    setup_logging(WBRConfig(log_level="DEBUG"))
    tid = new_trace_id()
    set_trace_id(tid)
    lg = get_logger("wbr.test.json2")
    lg.info("hello %s", "world", extra={"k": "v"})
    record = caplog.records[-1]
    line = JsonFormatter().format(record)
    obj = json.loads(line)  # 单行可解析
    assert obj["message"] == "hello world"
    assert obj["level"] == "INFO"
    assert obj["trace_id"] == tid
    assert obj["extra"]["k"] == "v"


def test_setup_logging_idempotent():
    reset_logging()
    root = logging.getLogger()
    before = len(root.handlers)
    setup_logging(WBRConfig())
    setup_logging(WBRConfig())
    assert len(root.handlers) == before + 1  # 幂等：只新增一次
    reset_logging()
