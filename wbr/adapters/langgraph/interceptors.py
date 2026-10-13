"""输出拦截器与工具权限门（SPEC-003 §1.3/1.4）。

- SchemaValidationInterceptor / ForbiddenDetectorInterceptor 均可独立开关。
- ToolPermissionGate：deny_by_default 下未列白名单一律拒绝。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.contract.models import RoleContract
from wbr.core.exceptions import ToolPermissionDeniedError
from wbr.core.schema.validator import validate as schema_validate
from wbr.core.security.guard import InjectionDetector


class InterceptResult(BaseModel):
    allowed: bool
    kind: str = ""          # schema | forbidden | ""
    detail: str = ""
    audited: bool = False


class SchemaValidationInterceptor:
    def __init__(self, *, enabled: bool = True, audit: AuditTrail | None = None) -> None:
        self.enabled = enabled
        self._audit = audit

    def check(self, contract: RoleContract, output: dict) -> InterceptResult:
        if not self.enabled or not contract.output_spec.schema_:
            return InterceptResult(allowed=True)
        errors = schema_validate(output, contract.output_spec.schema_)
        if not errors:
            return InterceptResult(allowed=True)
        detail = "; ".join(f"{e.path}: {e.message}" for e in errors[:5])
        self._emit(contract, AuditEventType.SCHEMA_VIOLATION, detail)
        return InterceptResult(allowed=False, kind="schema", detail=detail, audited=True)

    def _emit(self, contract: RoleContract, event_type, detail: str) -> None:
        if self._audit is not None:
            self._audit.append(
                AuditEvent(event_type=event_type, trace_id="no-trace",
                           role_id=contract.role_id, payload={"detail": detail})
            )


class ForbiddenDetectorInterceptor:
    """禁区违规检测：行为/领域关键词命中即拦截（V1 关键词规则）。"""

    def __init__(self, *, enabled: bool = True, audit: AuditTrail | None = None,
                 detector: InjectionDetector | None = None) -> None:
        self.enabled = enabled
        self._audit = audit
        self._detector = detector

    def check(self, contract: RoleContract, text: str) -> InterceptResult:
        if not self.enabled or contract.forbidden.is_empty():
            return InterceptResult(allowed=True)
        hits = [b for b in contract.forbidden.behaviors if b and b in text]
        hits += [d for d in contract.forbidden.domains if d and d in text]
        if not hits:
            return InterceptResult(allowed=True)
        detail = "命中禁区: " + ", ".join(hits)
        if self._audit is not None:
            self._audit.append(
                AuditEvent(event_type=AuditEventType.FORBIDDEN_VIOLATION, trace_id="no-trace",
                           role_id=contract.role_id, payload={"detail": detail})
            )
        return InterceptResult(allowed=False, kind="forbidden", detail=detail, audited=True)


class ToolDecision(BaseModel):
    allowed: bool
    tool: str
    reason: str = ""


class ToolPermissionGate:
    """FunctionCall 前置权限校验：声明式白名单，拒绝即审计。"""

    def __init__(self, *, audit: AuditTrail | None = None, strict: bool = False) -> None:
        self._audit = audit
        self._strict = strict

    def check(self, contract: RoleContract, tool_name: str) -> ToolDecision:
        policy = contract.tool_policy
        allowed = (not policy.deny_by_default) or (tool_name in policy.whitelist)
        self._emit(contract, tool_name, allowed)
        if allowed:
            return ToolDecision(allowed=True, tool=tool_name)
        reason = (
            f"角色 {contract.role_id} 未被授权使用工具 {tool_name!r}"
            f"（白名单={policy.whitelist}, deny_by_default={policy.deny_by_default}）"
        )
        if self._strict:
            raise ToolPermissionDeniedError(reason, details={"tool": tool_name, "role_id": contract.role_id})
        return ToolDecision(allowed=False, tool=tool_name, reason=reason)

    def _emit(self, contract: RoleContract, tool_name: str, allowed: bool) -> None:
        if self._audit is not None:
            self._audit.append(
                AuditEvent(event_type=AuditEventType.TOOL_CALL, trace_id="no-trace",
                           role_id=contract.role_id,
                           payload={"tool": tool_name, "allowed": allowed})
            )
