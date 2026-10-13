"""Harness 黄金用例库（SPEC-004 §1.1）。"""
from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wbr.core.exceptions import HarnessError


class GoldenCase(BaseModel):
    """一条黄金回归用例。"""

    model_config = ConfigDict(validate_assignment=True)

    case_id: str = Field(pattern=r"^[a-zA-Z0-9_\-\.]{1,128}$")
    question: str = Field(min_length=1)
    expected_keywords: list[str] = Field(default_factory=list)
    expected_schema: dict[str, Any] | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    expert_role_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    expect_disagreement: bool = False  # 构造为含分歧的用例（用于分歧检出率）

    @model_validator(mode="after")
    def _case_id_required(self) -> "GoldenCase":
        return self


class CaseSuite(BaseModel):
    """黄金用例库：case_id 唯一，可持久化。"""

    suite_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    version: str = "1.0.0"
    cases: list[GoldenCase] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    @model_validator(mode="after")
    def _unique_case_ids(self) -> "CaseSuite":
        ids = [c.case_id for c in self.cases]
        if len(ids) != len(set(ids)):
            raise HarnessError("用例 case_id 必须唯一", code="E7003")
        return self

    def add(self, case: GoldenCase) -> "CaseSuite":
        if any(c.case_id == case.case_id for c in self.cases):
            raise HarnessError(f"case_id 已存在: {case.case_id}", code="E7003")
        self.cases.append(case)
        return self

    def content_hash(self) -> str:
        from wbr.core.canonical import canonical_json, sha256_hex

        return sha256_hex(canonical_json([c.model_dump() for c in self.cases]))

    def save(self, path: str) -> None:
        from pathlib import Path

        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "CaseSuite":
        from pathlib import Path

        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
