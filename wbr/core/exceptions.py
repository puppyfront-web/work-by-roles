"""全局异常体系：统一 code / trace_id / 序列化（SPEC-001 §2.2）。"""
from __future__ import annotations

from typing import Any


class WBRError(Exception):
    """所有 wbr 异常的基类。"""

    default_code: str = "E0000"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        trace_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.trace_id = trace_id
        self.details: dict[str, Any] = details or {}

    def __str__(self) -> str:
        base = f"[{self.code}] {self.message}"
        if self.trace_id:
            base = f"{base} (trace_id={self.trace_id})"
        return base

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "trace_id": self.trace_id,
            "details": self.details,
        }


class ConfigError(WBRError):
    default_code = "E1001"


class ContractValidationError(WBRError):
    default_code = "E2001"


class ContractCompileError(WBRError):
    default_code = "E2002"


class SchemaValidationError(WBRError):
    default_code = "E2003"


class ForbiddenViolationError(WBRError):
    default_code = "E2004"


class MemoryPermissionDeniedError(WBRError):
    default_code = "E3001"


class SecurityViolationError(WBRError):
    default_code = "E4001"


class TokenBudgetExceededError(WBRError):
    default_code = "E5001"


class OrchestrationError(WBRError):
    default_code = "E6001"


class HarnessError(WBRError):
    default_code = "E7001"


class CacheError(WBRError):
    default_code = "E7002"


class AdapterError(WBRError):
    default_code = "E8001"


class ToolPermissionDeniedError(WBRError):
    default_code = "E8002"


class AppError(WBRError):
    default_code = "E9001"
