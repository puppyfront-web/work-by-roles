"""RoleContract 角色契约模型（SPEC-002 §1，最终版，长期不改）。

契约优先：一切角色行为约束均声明于此，禁止业务硬编码（全局规则6）。
可序列化 / 可哈希定版 / 可版本 Diff / 可持久化（全局规则7）。
"""
from __future__ import annotations

import datetime as _dt
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from wbr.core.canonical import canonical_json, sha256_hex
from wbr.core.constants import MemoryLayer
from wbr.core.loop_config import InnerLoopConfig, IntentPolicy

_SEMVER = r"^\d+\.\d+\.\d+$"
_ROLE_ID = r"^[a-z][a-z0-9_]{2,63}$"


class RoleType(str, Enum):
    COORDINATOR = "coordinator"
    EXPERT = "expert"
    VERIFIER = "verifier"


class RoleIdentity(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    role_id: str = Field(pattern=_ROLE_ID)
    name: str = Field(min_length=1, max_length=128)
    role_type: RoleType
    description: str = ""


class SopStep(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    step_id: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    title: str = Field(min_length=1, max_length=256)
    instruction: str = Field(min_length=1)
    expected_output: str = ""


class Sop(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    steps: list[SopStep] = Field(min_length=1)

    @field_validator("steps")
    @classmethod
    def _unique_step_ids(cls, v: list[SopStep]) -> list[SopStep]:
        ids = [s.step_id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError("step_id 必须唯一")
        return v


class ForbiddenRule(BaseModel):
    """禁区规则：禁止行为 + 禁止回答域。"""

    model_config = ConfigDict(validate_assignment=True)

    behaviors: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.behaviors and not self.domains


class OutputSpec(BaseModel):
    model_config = ConfigDict(validate_assignment=True, populate_by_name=True)

    schema_: dict[str, Any] = Field(alias="schema", default_factory=dict)
    strict: bool = True
    examples: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceSpec(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    required: bool = False
    citation_format: str = "[^n]"
    min_citations: int = Field(default=0, ge=0)


class ToolPolicy(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    whitelist: list[str] = Field(default_factory=list)
    deny_by_default: bool = True

    @property
    def all_denied(self) -> bool:
        return self.deny_by_default and not self.whitelist


class MemoryPermissions(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    read_layers: list[MemoryLayer] = Field(default_factory=list)
    write_layers: list[MemoryLayer] = Field(default_factory=list)
    allow_global_write: bool = False  # GLOBAL_SHARED 写的第二道显式授权


class TokenQuota(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    max_prompt_tokens: int = Field(default=6000, gt=0)
    max_completion_tokens: int = Field(default=2000, gt=0)
    max_turn_tokens: int = Field(default=8000, gt=0)


class ReviewDimension(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(min_length=1, max_length=64)
    description: str = ""
    weight: float = Field(gt=0.0, le=1.0)
    pass_threshold: float = Field(gt=0.0, le=1.0)


class ReviewCriteria(BaseModel):
    """评审标准：仅 Verifier 可持有。"""

    model_config = ConfigDict(validate_assignment=True)

    dimensions: list[ReviewDimension] = Field(min_length=1)
    overall_pass_threshold: float = Field(gt=0.0, le=1.0)

    @field_validator("dimensions")
    @classmethod
    def _unique_names(cls, v: list[ReviewDimension]) -> list[ReviewDimension]:
        names = [d.name for d in v]
        if len(names) != len(set(names)):
            raise ValueError("评审维度名必须唯一")
        return v


class ContractMeta(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    version: str = Field(default="1.0.0", pattern=_SEMVER)
    content_hash: str = ""
    created_at: _dt.datetime = Field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc))
    updated_at: _dt.datetime = Field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc))
    changelog: list[str] = Field(default_factory=list)


class RoleContract(BaseModel):
    """角色契约：身份/职责SOP/禁区/输出Schema/证据规范/工具权限/记忆权限/Token配额/评审标准/版本。"""

    model_config = ConfigDict(validate_assignment=True)

    identity: RoleIdentity
    sop: Sop
    forbidden: ForbiddenRule = Field(default_factory=ForbiddenRule)
    output_spec: OutputSpec = Field(default_factory=OutputSpec)
    evidence_spec: EvidenceSpec = Field(default_factory=EvidenceSpec)
    tool_policy: ToolPolicy = Field(default_factory=ToolPolicy)
    memory_permissions: MemoryPermissions = Field(default_factory=MemoryPermissions)
    token_quota: TokenQuota = Field(default_factory=TokenQuota)
    review_criteria: ReviewCriteria | None = None
    intent_policy: IntentPolicy | None = None      # Coordinator 语义
    inner_loop: InnerLoopConfig | None = None      # Expert/Verifier 语义
    meta: ContractMeta = Field(default_factory=ContractMeta)

    # ---- 跨字段校验 ----
    @model_validator(mode="after")
    def _validate_role_type_rules(self) -> RoleContract:
        if self.identity.role_type == RoleType.VERIFIER and self.review_criteria is None:
            raise ValueError("Verifier 角色必须声明 review_criteria")
        if self.identity.role_type == RoleType.COORDINATOR and self.review_criteria is not None:
            raise ValueError("Coordinator 角色不得持有 review_criteria")
        return self

    # ---- 便捷属性 ----
    @property
    def role_id(self) -> str:
        return self.identity.role_id

    @property
    def role_type(self) -> RoleType:
        return self.identity.role_type

    @property
    def content_hash(self) -> str:
        return self.meta.content_hash

    # ---- 构建 / 定版 ----
    @classmethod
    def build(cls, **kw: Any) -> RoleContract:
        """构建契约并计算内容哈希（业务字段定版，meta 不参与）。"""
        contract = cls(**kw)
        contract.meta.content_hash = cls.compute_hash(contract)
        return contract

    @staticmethod
    def compute_hash(contract: RoleContract) -> str:
        payload = contract.model_dump(exclude={"meta"}, by_alias=True)
        return sha256_hex(canonical_json(payload))

    def refresh_hash(self) -> None:
        self.meta.content_hash = self.compute_hash(self)

    # ---- 序列化 ----
    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, exclude_none=False)

    @classmethod
    def from_json(cls, raw: str | bytes) -> RoleContract:
        return cls.model_validate_json(raw)

    def save(self, path: str) -> None:
        from pathlib import Path

        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> RoleContract:
        from pathlib import Path

        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    # ---- 版本派生 ----
    def with_changes(
        self,
        *,
        bump: Literal["major", "minor", "patch"] = "patch",
        changelog: str | None = None,
        **kw: Any,
    ) -> RoleContract:
        """派生新版本契约（copy-on-write）：版本号 bump、哈希重算、changelog 追加。

        支持顶层字段与点路径嵌套更新，如 ``identity.description="..."``、
        ``forbidden.behaviors=[...]``（列表整体替换）。
        """
        data = self.model_dump(by_alias=True)
        for key, value in kw.items():
            self._set_path(data, key.split("."), value)
        new = RoleContract.model_validate(data)
        new.meta = ContractMeta(
            version=_bump_version(self.meta.version, bump),
            created_at=self.meta.created_at,
            updated_at=_dt.datetime.now(_dt.timezone.utc),
            changelog=[*self.meta.changelog, *( [changelog] if changelog else [] )],
        )
        new.meta.content_hash = self.compute_hash(new)
        return new

    @staticmethod
    def _set_path(data: dict[str, Any], path: list[str], value: Any) -> None:
        node = data
        for seg in path[:-1]:
            if not isinstance(node, dict) or seg not in node:
                raise ValueError(f"未知契约字段路径: {'.'.join(path)}")
            node = node[seg]
        leaf = path[-1]
        if not isinstance(node, dict) or leaf not in node:
            raise ValueError(f"未知契约字段: {'.'.join(path)}")
        node[leaf] = value


def _bump_version(version: str, part: Literal["major", "minor", "patch"]) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"
