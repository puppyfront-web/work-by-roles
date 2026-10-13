"""wbr · work-by-roles 专家团治理系统。

三层架构：wbr.core（内核，框架无关）→ wbr.adapters（第三方适配）→ wbr.app（API/画布）。
Core 仅依赖 stdlib + Pydantic V2（SPEC-000 D-01）。
"""
from __future__ import annotations

__version__ = "1.0.0"

# ---- 基础设施 ----
from wbr.core.audit_bus import AuditBus, AuditEvent as BusAuditEvent
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

# ---- 契约 ----
from wbr.core.contract import (
    CompiledPrompt,
    ContractChange,
    ContractCompiler,
    ContractDiffEngine,
    ContractMeta,
    DiffReport,
    EvidenceSpec,
    ForbiddenRule,
    MemoryPermissions,
    OutputSpec,
    ReviewCriteria,
    ReviewDimension,
    RoleContract,
    RoleIdentity,
    RoleType,
    Sop,
    SopStep,
    TokenQuota,
    ToolPolicy,
)

# ---- 审计 ----
from wbr.core.audit import AuditEvent, AuditEventType, AuditTrail, RoleBehaviorRecord
from wbr.core.audit.pack import AuditPack, AuditPackBuilder

# ---- 记忆 / 编排 ----
from wbr.core.memory import InMemoryMemoryStore, MemoryHub, MemoryRecord, MemoryStore
from wbr.core.orchestration import (
    ApprovalStateMachine,
    Disagreement,
    ExpertOutcome,
    ExpertStatus,
    ModelInvoker,
    ModelRequest,
    ModelResponse,
    ReviewResult,
    ReviewSession,
    ReviewStatus,
    ScriptedInvoker,
    TokenUsage,
    Verdict,
    Violation,
    ViolationKind,
)

# ---- 安全 / Token / 缓存 ----
from wbr.core.security import (
    InjectionDetector,
    InjectionReport,
    RiskLevel,
    guard_user_input,
    wrap_external_content,
)
from wbr.core.token import (
    BudgetPolicy,
    HeuristicTokenCounter,
    TokenBudget,
    TokenCounter,
    TokenMeter,
)
from wbr.core.cache import ContractBoundCache, InMemoryCacheBackend

# ---- Harness ----
from wbr.core.harness import (
    BaselineSnapshot,
    CaseResult,
    CaseSuite,
    GoldenCase,
    HarnessMetrics,
    HeuristicJudge,
    RegressionEngine,
    RegressionReport,
)

__all__ = [
    "__version__",
    # 基础设施
    "AuditBus", "BusAuditEvent", "WBRConfig",
    "new_trace_id", "get_trace_id", "set_trace_id",
    # 异常
    "WBRError", "ConfigError", "ContractValidationError", "ContractCompileError",
    "SchemaValidationError", "ForbiddenViolationError", "MemoryPermissionDeniedError",
    "SecurityViolationError", "TokenBudgetExceededError", "OrchestrationError",
    "HarnessError", "CacheError", "AdapterError", "ToolPermissionDeniedError", "AppError",
    # 契约
    "RoleContract", "RoleIdentity", "RoleType", "Sop", "SopStep", "ForbiddenRule",
    "OutputSpec", "EvidenceSpec", "ToolPolicy", "MemoryPermissions", "TokenQuota",
    "ReviewCriteria", "ReviewDimension", "ContractMeta",
    "ContractCompiler", "CompiledPrompt", "ContractDiffEngine", "DiffReport", "ContractChange",
    # 审计
    "AuditEvent", "AuditEventType", "AuditTrail", "RoleBehaviorRecord",
    "AuditPack", "AuditPackBuilder",
    # 记忆 / 编排
    "MemoryHub", "MemoryRecord", "MemoryStore", "InMemoryMemoryStore",
    "ModelInvoker", "ModelRequest", "ModelResponse", "TokenUsage", "ScriptedInvoker",
    "ReviewSession", "ReviewResult", "ExpertOutcome", "ExpertStatus",
    "Verdict", "Violation", "ViolationKind", "Disagreement", "ReviewStatus",
    "ApprovalStateMachine",
    # 安全 / Token / 缓存
    "InjectionDetector", "InjectionReport", "RiskLevel", "guard_user_input", "wrap_external_content",
    "TokenCounter", "HeuristicTokenCounter", "TokenMeter", "BudgetPolicy", "TokenBudget",
    "ContractBoundCache", "InMemoryCacheBackend",
    # Harness
    "GoldenCase", "CaseSuite", "CaseResult", "BaselineSnapshot",
    "RegressionEngine", "RegressionReport", "HarnessMetrics", "HeuristicJudge",
]
