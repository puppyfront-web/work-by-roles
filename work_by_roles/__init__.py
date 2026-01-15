"""
Multi-Role Skills Workflow Framework

A framework to enforce role-based workflows and quality gates.
"""

# Import directly from core.engine to avoid circular import issues
from .core.engine import (
    WorkflowEngine,
    WorkflowError,
    ValidationError,
    StageStatus,
    RoleManager,
    WorkflowExecutor,
    ProjectScanner,
    Skill,
    Role,
    Stage,
    Workflow as WorkflowBase,
    Agent,
    AgentOrchestrator,
    AgentContext,
)
from .quick_start import Workflow

# ContextSummary is available in workflow_engine.py for advanced users
# Import it directly if needed: from workflow_engine import ContextSummary

__version__ = "0.1.0"
__all__ = [
    "WorkflowEngine",
    "WorkflowError",
    "ValidationError",
    "StageStatus",
    "RoleManager",
    "WorkflowExecutor",
    "ProjectScanner",
    "Skill",
    "Role",
    "Stage",
    "WorkflowBase",
    "Workflow",  # High-level API (recommended)
    "Agent",
    "AgentOrchestrator",
    "AgentContext",
    # ContextSummary available via: from workflow_engine import ContextSummary
]

