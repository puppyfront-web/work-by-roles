"""JSON Schema 子集校验器（SPEC-000 D-08，零依赖、可全量测试）。

支持关键字：type（含数组形式）、enum、properties、required、items、
additionalProperties(false)、minLength、maxLength、minimum、maximum。
不支持的关键字被忽略（宽松通过），错误路径以 JSON Pointer 风格给出。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


@dataclass(frozen=True)
class SchemaError:
    path: str          # JSON Pointer 风格，如 /items/0/name；根为 ""
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


def _type_ok(value: Any, type_name: str) -> bool:
    expected = _TYPE_MAP.get(type_name)
    if expected is None:
        return True  # 未知类型名宽松放过
    if type_name == "number" and isinstance(value, bool):
        return False  # bool 是 int 子类，需排除
    if type_name == "integer" and isinstance(value, bool):
        return False
    return isinstance(value, expected)


def validate(instance: Any, schema: dict[str, Any]) -> list[SchemaError]:
    """校验实例，返回错误列表（空列表 = 通过）。永不抛异常。"""
    errors: list[SchemaError] = []
    _validate(instance, schema, "", errors)
    return errors


def _validate(instance: Any, schema: dict[str, Any], path: str, errors: list[SchemaError]) -> None:
    if not isinstance(schema, dict):
        return
    type_spec = schema.get("type")
    if type_spec is not None:
        names = type_spec if isinstance(type_spec, list) else [type_spec]
        if not any(_type_ok(instance, str(n)) for n in names):
            errors.append(
                SchemaError(path, f"expected type {'/'.join(map(str, names))}, got {type(instance).__name__}")
            )
            return  # 类型不符时不再深入结构检查

    enum_spec = schema.get("enum")
    if enum_spec is not None and instance not in enum_spec:
        errors.append(SchemaError(path, f"value {instance!r} not in enum {enum_spec!r}"))

    if isinstance(instance, str):
        _validate_string(instance, schema, path, errors)
    elif isinstance(instance, (int, float)) and not isinstance(instance, bool):
        _validate_number(instance, schema, path, errors)
    elif isinstance(instance, dict):
        _validate_object(instance, schema, path, errors)
    elif isinstance(instance, list):
        _validate_array(instance, schema, path, errors)


def _validate_string(value: str, schema: dict[str, Any], path: str, errors: list[SchemaError]) -> None:
    min_len = schema.get("minLength")
    if isinstance(min_len, int) and len(value) < min_len:
        errors.append(SchemaError(path, f"length {len(value)} < minLength {min_len}"))
    max_len = schema.get("maxLength")
    if isinstance(max_len, int) and len(value) > max_len:
        errors.append(SchemaError(path, f"length {len(value)} > maxLength {max_len}"))


def _validate_number(value: float, schema: dict[str, Any], path: str, errors: list[SchemaError]) -> None:
    minimum = schema.get("minimum")
    if isinstance(minimum, (int, float)) and value < minimum:
        errors.append(SchemaError(path, f"{value} < minimum {minimum}"))
    maximum = schema.get("maximum")
    if isinstance(maximum, (int, float)) and value > maximum:
        errors.append(SchemaError(path, f"{value} > maximum {maximum}"))


def _validate_object(value: dict[str, Any], schema: dict[str, Any], path: str, errors: list[SchemaError]) -> None:
    props: dict[str, Any] = schema.get("properties", {}) or {}
    required: list[str] = schema.get("required", []) or []
    for key in required:
        if key not in value:
            errors.append(SchemaError(path, f"missing required property {key!r}"))
    additional = schema.get("additionalProperties", True)
    for key, sub in value.items():
        child_path = f"{path}/{key}"
        if key in props:
            _validate(sub, props[key], child_path, errors)
        elif additional is False:
            errors.append(SchemaError(child_path, "additionalProperties is false"))
        elif isinstance(additional, dict):
            _validate(sub, additional, child_path, errors)


def _validate_array(value: list[Any], schema: dict[str, Any], path: str, errors: list[SchemaError]) -> None:
    items = schema.get("items")
    if isinstance(items, dict):
        for idx, item in enumerate(value):
            _validate(item, items, f"{path}/{idx}", errors)
