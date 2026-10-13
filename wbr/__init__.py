"""wbr · work-by-roles 专家团治理系统。

三层架构：wbr.core（内核，框架无关）→ wbr.adapters（第三方适配）→ wbr.app（API/画布）。
Core 仅依赖 stdlib + Pydantic V2（SPEC-000 D-01）。
"""
from __future__ import annotations

__version__ = "0.3.0"

from wbr.core.audit_bus import AuditBus, AuditEvent
from wbr.core.config import WBRConfig
from wbr.core.context import get_trace_id, new_trace_id, set_trace_id
from wbr.core.exceptions import (
    AdapterError,
    AppError,
    CacheError,
    ConfigError,
    ContractCompileError,
    ContractValidationError,
    ForbiddenViolationError,
    HarnessError,
    MemoryPermissionDeniedError,
    OrchestrationError,
    SchemaValidationError,
    SecurityViolationError,
    TokenBudgetExceededError,
    ToolPermissionDeniedError,
    WBRError,
)

__all__ = [
    "__version__",
    "AuditBus",
    "AuditEvent",
    "WBRConfig",
    "WBRError",
    "ConfigError",
    "ContractValidationError",
    "ContractCompileError",
    "SchemaValidationError",
    "ForbiddenViolationError",
    "MemoryPermissionDeniedError",
    "SecurityViolationError",
    "TokenBudgetExceededError",
    "OrchestrationError",
    "HarnessError",
    "CacheError",
    "AdapterError",
    "ToolPermissionDeniedError",
    "AppError",
    "new_trace_id",
    "get_trace_id",
    "set_trace_id",
]
