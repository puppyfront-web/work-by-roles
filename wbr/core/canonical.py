"""Canonical JSON 与内容哈希（SPEC-000 D-09）。

canonical_json：排序键、ensure_ascii=False、紧凑分隔符。
哈希：sha256(canonical_json(obj)) 的 hex 摘要。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(obj: Any) -> str:
    if isinstance(obj, str):
        payload = obj.encode("utf-8")
    else:
        payload = canonical_json(obj).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def digest_of_text(text: str, *, bytes_len: int = 16) -> str:
    """文本摘要（行为审计记录用，截断 hex）。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:bytes_len]
