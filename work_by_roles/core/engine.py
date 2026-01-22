"""
Multi-Role Skills Workflow Engine
Core Framework Implementation (Backward Compatibility Layer)

This module has been refactored. All major classes have been moved to separate modules.
This file is kept for backward compatibility to allow importing from work_by_roles.core.engine.
"""

from .exceptions import ValidationError, WorkflowError, SecurityError
from .enums import StageStatus, SkillErrorType, SkillWorkflowStepStatus
from .models import (
    Skill, SkillExecution, SkillRequirement, SkillBundle,
    ConditionalBranch, LoopConfig, SkillStepConfig, SkillStep,
    SkillWorkflowTrigger, SkillWorkflowConfig, SkillWorkflow,
    SkillWorkflowExecution, Role, QualityGate, Output, Stage,
    Workflow, ExecutionState, ProjectContext, AgentContext,
    ContextSummary
)
from .variable_resolver import VariableResolver
from .project_scanner import ProjectScanner
from .schema_loader import SchemaLoader, normalize_path
from .config_loader import ConfigLoader
from .role_manager import RoleManager
from .workflow_executor import WorkflowExecutor
from .state_storage import StateStorage, FileStateStorage
from .team_manager import TeamManager
from .quality_gates import QualityGateSystem
from .workflow_engine import WorkflowEngine
from .execution_tracker import ExecutionTracker
from .skill_selector import SkillSelector, RetryHandler
from .intent_router import IntentRouter
from .agent import Agent
from .skill_invoker import SkillInvoker, PlaceholderSkillInvoker, LLMSkillInvoker, CompositeSkillInvoker
from .condition_evaluator import ConditionEvaluator
from .skill_workflow_executor import SkillWorkflowExecutor
from .role_executor import RoleExecutor
from .skill_benchmark import SkillBenchmark
from .agent_orchestrator import AgentOrchestrator
from .project_manager import ProjectManager

# Re-export for backward compatibility
__all__ = [
    'ValidationError', 'WorkflowError', 'SecurityError',
    'StageStatus', 'SkillErrorType', 'SkillWorkflowStepStatus',
    'Skill', 'SkillExecution', 'SkillRequirement', 'SkillBundle',
    'ConditionalBranch', 'LoopConfig', 'SkillStepConfig', 'SkillStep',
    'SkillWorkflowTrigger', 'SkillWorkflowConfig', 'SkillWorkflow',
    'SkillWorkflowExecution', 'Role', 'QualityGate', 'Output', 'Stage',
    'Workflow', 'ExecutionState', 'ProjectContext', 'AgentContext',
    'ContextSummary', 'ExecutionTracker', 'SkillSelector', 'RetryHandler',
    'ConditionEvaluator', 'VariableResolver', 'AgentOrchestrator',
    'ProjectScanner', 'SchemaLoader', 'ConfigLoader', 'RoleManager',
    'WorkflowExecutor', 'StateStorage', 'FileStateStorage',
    'TeamManager', 'QualityGateSystem', 'WorkflowEngine',
    'IntentRouter', 'Agent', 'SkillInvoker', 'PlaceholderSkillInvoker',
    'LLMSkillInvoker', 'CompositeSkillInvoker', 'SkillWorkflowExecutor',
    'RoleExecutor', 'SkillBenchmark', 'normalize_path', 'ProjectManager'
]

# Note: The following classes were previously defined here but are now in separate modules.
# They are imported above and re-exported.
