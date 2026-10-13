"""契约版本 Diff 引擎（SPEC-002 §3）：字段级对比 + 变更分类 + 破坏性判定。"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.contract.models import RoleContract


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class ChangeCategory(str, Enum):
    FIELD = "field"        # 描述、身份等一般字段
    RULE = "rule"          # SOP 职责规则
    SCHEMA = "schema"      # 输出 Schema
    FORBIDDEN = "forbidden"  # 禁区
    POLICY = "policy"      # 工具/记忆/Token 权限策略


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContractChange(BaseModel):
    path: str
    change_type: ChangeType
    category: ChangeCategory
    severity: Severity = Severity.LOW
    old: Any = None
    new: Any = None


class DiffReport(BaseModel):
    contract_id: str
    from_version: str
    to_version: str
    changes: list[ContractChange] = Field(default_factory=list)

    @property
    def has_breaking(self) -> bool:
        return any(c.severity == Severity.HIGH for c in self.changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "has_breaking": self.has_breaking,
            "changes": [c.model_dump() for c in self.changes],
        }


# 顶层字段 → 类别
_CATEGORY: dict[str, ChangeCategory] = {
    "identity": ChangeCategory.FIELD,
    "sop": ChangeCategory.RULE,
    "forbidden": ChangeCategory.FORBIDDEN,
    "output_spec": ChangeCategory.SCHEMA,
    "tool_policy": ChangeCategory.POLICY,
    "memory_permissions": ChangeCategory.POLICY,
    "token_quota": ChangeCategory.POLICY,
    "evidence_spec": ChangeCategory.POLICY,
}


class ContractDiffEngine:
    """对两份契约做递归字段级 Diff（列表按身份键/标量值对齐）。"""

    # 复杂对象列表按身份键对齐；标量列表按值对齐（"@scalar"）
    LIST_KEYS = {("sop", "steps"): "step_id"}
    SCALAR_LISTS = {
        "forbidden.behaviors",
        "forbidden.domains",
        "tool_policy.whitelist",
        "identity.read_layers",
        "identity.write_layers",
    }

    def diff(self, old: RoleContract, new: RoleContract) -> DiffReport:
        old_d = old.model_dump(by_alias=True, exclude={"meta"})
        new_d = new.model_dump(by_alias=True, exclude={"meta"})
        changes: list[ContractChange] = []
        self._walk("", old_d, new_d, changes)
        return DiffReport(
            contract_id=old.role_id,
            from_version=old.meta.version,
            to_version=new.meta.version,
            changes=changes,
        )

    # ---- 递归对比 ----
    def _walk(self, prefix: str, old: Any, new: Any, changes: list[ContractChange]) -> None:
        if isinstance(old, dict) and isinstance(new, dict):
            for key in sorted(set(old) | set(new)):
                path = f"{prefix}.{key}" if prefix else key
                if key not in old:
                    changes.append(self._make(path, ChangeType.ADDED, None, new[key]))
                elif key not in new:
                    changes.append(self._make(path, ChangeType.REMOVED, old[key], None))
                else:
                    self._walk(path, old[key], new[key], changes)
        elif isinstance(old, list) and isinstance(new, list):
            self._diff_lists(prefix, old, new, changes)
        elif old != new:
            changes.append(self._make(prefix, ChangeType.MODIFIED, old, new))

    def _diff_lists(self, prefix: str, old: list, new: list, changes: list[ContractChange]) -> None:
        key_field = self._list_key(prefix)
        if key_field == "@scalar":
            old_set, new_set = {str(v) for v in old}, {str(v) for v in new}
            for item in sorted(old_set - new_set):
                changes.append(self._make(f"{prefix}[{item}]", ChangeType.REMOVED, item, None))
            for item in sorted(new_set - old_set):
                changes.append(self._make(f"{prefix}[{item}]", ChangeType.ADDED, None, item))
            return
        if key_field is None:
            if old != new:
                changes.append(self._make(prefix, ChangeType.MODIFIED, old, new))
            return
        old_map = {item.get(key_field): item for item in old if isinstance(item, dict)}
        new_map = {item.get(key_field): item for item in new if isinstance(item, dict)}
        for kid in sorted(set(old_map) | set(new_map), key=str):
            path = f"{prefix}[{kid}]"
            if kid not in old_map:
                changes.append(self._make(path, ChangeType.ADDED, None, new_map[kid]))
            elif kid not in new_map:
                changes.append(self._make(path, ChangeType.REMOVED, old_map[kid], None))
            else:
                self._walk(path, old_map[kid], new_map[kid], changes)

    def _list_key(self, prefix: str) -> str | None:
        for (top, sub), key in self.LIST_KEYS.items():
            if prefix == f"{top}.{sub}" or prefix.startswith(f"{top}.{sub}."):
                return key
        if prefix in self.SCALAR_LISTS:
            return "@scalar"
        return None

    # ---- 分类与严重级 ----
    def _make(self, path: str, change_type: ChangeType, old: Any, new: Any) -> ContractChange:
        top = path.split(".")[0].split("[")[0]
        category = _CATEGORY.get(top, ChangeCategory.FIELD)
        severity = self._severity(top, path, change_type, old, new)
        return ContractChange(
            path=path, change_type=change_type, category=category, severity=severity, old=old, new=new
        )

    def _severity(
        self, top: str, path: str, ct: ChangeType, old: Any, new: Any
    ) -> Severity:
        if top == "forbidden":
            # 放宽禁区（删除/缩减）是破坏性变更
            if ct == ChangeType.REMOVED:
                return Severity.HIGH
            if ct == ChangeType.MODIFIED and isinstance(old, str) and isinstance(new, str):
                return Severity.MEDIUM
            return Severity.MEDIUM
        if top == "output_spec":
            if "required" in path:
                return Severity.HIGH  # required 变更（收紧或放宽）均破坏兼容
            if ct in (ChangeType.ADDED, ChangeType.MODIFIED) and ("schema" in path or "strict" in path):
                return Severity.MEDIUM
            return Severity.LOW
        if top in ("tool_policy", "memory_permissions"):
            if ct in (ChangeType.ADDED, ChangeType.MODIFIED) and any(
                k in path for k in ("whitelist", "read_layers", "write_layers", "allow_global_write")
            ):
                return Severity.HIGH  # 权限扩大
            if ct == ChangeType.REMOVED:
                return Severity.MEDIUM
            return Severity.LOW
        if top == "identity" and "role_type" in path:
            return Severity.HIGH
        if top == "sop":
            return Severity.MEDIUM
        return Severity.LOW
