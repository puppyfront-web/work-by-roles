"""State 元数据注入：只写 wbr__meta 命名空间，绝不触碰用户原有键（SPEC-003 §1.2）。"""
from __future__ import annotations

from typing import Any

WBR_META_KEY = "wbr__meta"


def inject_meta(state: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """返回注入元数据后的新 State（浅拷贝 + 命名空间键），用户键保持原对象不变。"""
    merged = dict(state.get(WBR_META_KEY) or {})
    merged.update(meta)
    out = dict(state)
    out[WBR_META_KEY] = merged
    return out


def read_meta(state: dict[str, Any]) -> dict[str, Any]:
    meta = state.get(WBR_META_KEY)
    return dict(meta) if isinstance(meta, dict) else {}


def merge_state(orig: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """深合并：dict 递归合并、其余覆盖；不修改入参。"""
    out = dict(orig)
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_state(out[k], v)
        else:
            out[k] = v
    return out
