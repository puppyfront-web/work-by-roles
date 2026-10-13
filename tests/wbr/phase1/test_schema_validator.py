"""TC-1-SCHEMA-1/2：JSON Schema 子集校验器。"""
from __future__ import annotations

import pytest

from wbr.core.schema.validator import validate


def test_object_required_and_properties_pass():
    schema = {
        "type": "object",
        "required": ["conclusion", "confidence"],
        "properties": {
            "conclusion": {"type": "string", "minLength": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "citations": {"type": "array", "items": {"type": "string"}},
        },
    }
    ok = {"conclusion": "x", "confidence": 0.9, "citations": ["a", "b"]}
    assert validate(ok, schema) == []


@pytest.mark.parametrize(
    ("bad", "err_frag", "err_path"),
    [
        ({"confidence": 0.9}, "missing required", ""),                       # 缺 conclusion
        ({"conclusion": "x", "confidence": "high"}, "expected type", "/confidence"),
        ({"conclusion": "", "confidence": 0.5}, "minLength", "/conclusion"),
        ({"conclusion": "x", "confidence": 1.5}, "maximum", "/confidence"),
        ({"conclusion": "x", "confidence": -0.1}, "minimum", "/confidence"),
    ],
)
def test_object_violations(bad, err_frag, err_path):
    schema = {
        "type": "object",
        "required": ["conclusion", "confidence"],
        "properties": {
            "conclusion": {"type": "string", "minLength": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }
    errs = validate(bad, schema)
    assert errs and err_frag in errs[0].message
    assert errs[0].path == err_path


def test_array_items_and_enum():
    schema = {"type": "array", "items": {"type": "string", "enum": ["low", "high"]}}
    assert validate(["low", "high"], schema) == []
    errs = validate(["low", "medium"], schema)
    assert errs[0].path == "/1"
    assert "enum" in errs[0].message


def test_integer_boolean_edge():
    schema = {"type": "integer"}
    assert validate(3, schema) == []
    assert validate(True, schema)  # bool 不是 integer
    assert validate(3.5, schema)


def test_additional_properties_false():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": False}
    assert validate({"a": "x"}, schema) == []
    errs = validate({"a": "x", "b": 1}, schema)
    assert errs[0].path == "/b"


def test_unknown_keywords_ignored_and_nested_path():
    schema = {
        "type": "object",
        "properties": {
            "meta": {"type": "object", "properties": {"tag": {"type": "string"}}, "format": "date-time"},
        },
    }
    errs = validate({"meta": {"tag": 1}}, schema)
    assert errs[0].path == "/meta/tag"


def test_never_raises_on_weird_input():
    assert validate(None, {"type": "string"}) != []
    assert validate("x", {"type": ["string", "null"]}) == []
    assert validate(5, {"minLength": 3}) == []  # minLength 只作用于字符串
    assert validate({"a": 1}, {"type": "object", "required": []}) == []
