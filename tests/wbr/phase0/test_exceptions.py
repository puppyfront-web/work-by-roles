"""TC-0-EXC-1：全局异常体系统一性。"""
from __future__ import annotations

import json

import pytest

from wbr.core import exceptions as exc


EXPECTED = [
    (exc.ConfigError, "E1001"),
    (exc.ContractValidationError, "E2001"),
    (exc.ContractCompileError, "E2002"),
    (exc.SchemaValidationError, "E2003"),
    (exc.ForbiddenViolationError, "E2004"),
    (exc.MemoryPermissionDeniedError, "E3001"),
    (exc.SecurityViolationError, "E4001"),
    (exc.TokenBudgetExceededError, "E5001"),
    (exc.OrchestrationError, "E6001"),
    (exc.HarnessError, "E7001"),
    (exc.CacheError, "E7002"),
    (exc.AdapterError, "E8001"),
    (exc.ToolPermissionDeniedError, "E8002"),
    (exc.AppError, "E9001"),
]


@pytest.mark.parametrize(("cls", "code"), EXPECTED)
def test_exception_codes_and_str(cls, code):
    e = cls("boom", trace_id="wbr-abc", details={"k": 1})
    assert e.code == code
    assert e.trace_id == "wbr-abc"
    assert e.details == {"k": 1}
    text = str(e)
    assert f"[{code}]" in text
    assert "boom" in text
    assert "wbr-abc" in text


def test_hierarchy_catchable_as_base():
    with pytest.raises(exc.WBRError):
        raise exc.SchemaValidationError("bad schema")


def test_to_dict_serializable():
    e = exc.ConfigError("bad yaml", trace_id="t1", details={"path": "a.yaml"})
    d = e.to_dict()
    assert d["code"] == "E1001"
    assert json.loads(json.dumps(d))["message"] == "bad yaml"


def test_default_trace_id_none_ok():
    e = exc.AppError("x")
    assert e.code == "E9001"
    assert e.trace_id is None
