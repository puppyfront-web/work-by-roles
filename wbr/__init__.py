"""wbr · work-by-roles 专家团治理系统。

三层架构：wbr.core（内核，框架无关）→ wbr.adapters（第三方适配）→ wbr.app（API/画布）。
Core 仅依赖 stdlib + Pydantic V2（SPEC-000 D-01）。
"""
from __future__ import annotations

__version__ = "2.1.1"

# ---- 基础设施 ----
# ---- 审计 ----
from wbr.core.audit import AuditEvent, AuditEventType, AuditTrail, RoleBehaviorRecord
from wbr.core.audit.chain import ChainedEvent, ChainVerification, HashChainAuditor, HashChainTrail
from wbr.core.audit.pack import AuditPack, AuditPackBuilder
from wbr.core.audit_bus import AuditBus
from wbr.core.audit_bus import AuditEvent as BusAuditEvent
from wbr.core.bundle import BaselineBundle
from wbr.core.cache import ContractBoundCache, InMemoryCacheBackend
from wbr.core.cache.semantic import SemanticCache
from wbr.core.config import WBRConfig
from wbr.core.context import get_trace_id, new_trace_id, set_trace_id

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
from wbr.core.experiment import ABExperiment, ABReport, ABVariant

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
from wbr.core.harness.feedback import FeedbackLoop, FeedbackRecord
from wbr.core.harness.loop_metrics import (
    DebateLoopMetrics,
    IntentMetrics,
    LoopMetrics,
)
from wbr.core.knowledge import (
    KnowledgeBase,
    KnowledgeDocument,
    KnowledgeEvidenceCollector,
    KnowledgeSearchHit,
)
from wbr.core.loop_config import InnerLoopConfig, IntentPolicy, LoopSummarySnapshot

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
from wbr.core.orchestration.debate import (
    DebateConfig,
    DebateModerator,
    DebateResult,
    DebateTurn,
)
from wbr.core.orchestration.intent import (
    IntentPipeline,
    IntentResult,
    IntentType,
    NextAction,
)

# ---- 安全 / Token / 缓存 ----
from wbr.core.security import (
    InjectionDetector,
    InjectionReport,
    RiskControlPolicy,
    RiskDecision,
    RiskLevel,
    guard_user_input,
    wrap_external_content,
)
from wbr.core.security.redactor import RedactionReport, Redactor
from wbr.core.token import (
    BudgetPolicy,
    HeuristicTokenCounter,
    TokenBudget,
    TokenCounter,
    TokenMeter,
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
    # V1.x
    "Redactor", "RedactionReport", "RiskControlPolicy", "RiskDecision",
    "KnowledgeBase", "KnowledgeDocument", "KnowledgeEvidenceCollector", "KnowledgeSearchHit",
    "SemanticCache", "FeedbackLoop", "FeedbackRecord",
    # V2.0
    "HashChainAuditor", "HashChainTrail", "ChainedEvent", "ChainVerification",
    "BaselineBundle", "ABExperiment", "ABReport", "ABVariant",
    "DebateModerator", "DebateConfig", "DebateResult", "DebateTurn",
    "WorkspaceRegistry",
    # V2.1 意图与受控Loop
    "IntentPipeline", "IntentResult", "IntentType", "NextAction", "IntentPolicy",
    "InnerLoopConfig", "LoopSummarySnapshot",
    "IntentMetrics", "LoopMetrics", "DebateLoopMetrics",
]


def __getattr__(name: str):
    # 适配层惰性导出（不引入第三方依赖到 import wbr 路径）
    if name == "MCPToolBridge":
        from wbr.adapters.mcp.bridge import MCPToolBridge

        return MCPToolBridge
    if name == "OTelBridge":
        from wbr.adapters.observability.otel import OTelBridge

        return OTelBridge
    if name == "WorkspaceRegistry":
        from wbr.app.workspace import WorkspaceRegistry

        return WorkspaceRegistry
    raise AttributeError(name)
