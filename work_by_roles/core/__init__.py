"""
Core workflow engine modules.
Following SOLID principles - modules are organized by responsibility.
"""

# Exceptions
from .exceptions import ValidationError, WorkflowError, SecurityError

# Enums
from .enums import StageStatus, SkillErrorType, SkillWorkflowStepStatus, IntentType

# Models
from .models import (
    Skill, SkillExecution, SkillRequirement, SkillBundle,
    ConditionalBranch, LoopConfig, SkillStepConfig, SkillStep,
    SkillWorkflowTrigger, SkillWorkflowConfig, SkillWorkflow,
    SkillWorkflowExecution, Role, QualityGate, Output, Stage,
    Workflow, ExecutionState, ProjectContext, AgentContext,
    ContextSummary
)

# Execution tracking
from .execution_tracker import ExecutionTracker

# Skill selection
from .skill_selector import SkillSelector, RetryHandler

# Condition evaluation
from .condition_evaluator import ConditionEvaluator

# Variable resolution
from .variable_resolver import VariableResolver

# Import from separate modules
from .project_scanner import ProjectScanner
from .schema_loader import SchemaLoader, normalize_path
from .config_loader import ConfigLoader
from .role_manager import RoleManager
from .workflow_executor import WorkflowExecutor
from .state_storage import StateStorage, FileStateStorage
from .team_manager import TeamManager
from .quality_gates import QualityGateSystem
from .workflow_engine import WorkflowEngine
from .intent_router import IntentRouter
from .intent_agent import IntentAgent
from .bug_analysis_agent import BugAnalysisAgent
from .intent_handler import IntentHandler, handle_user_input
from .skill_workflow_executor import SkillWorkflowExecutor
from .agent_orchestrator import AgentOrchestrator
from .role_executor import RoleExecutor
from .skill_invoker import SkillInvoker, PlaceholderSkillInvoker, LLMSkillInvoker, CompositeSkillInvoker
from .agent import Agent
from .skill_benchmark import SkillBenchmark
from .task_router import TaskRouter

# Import remaining classes from engine.py for backward compatibility
from .engine import (
    SecurityError,
    AgentContext,
    ContextSummary,
    normalize_path,
)

__all__ = [
    # Exceptions
    'ValidationError',
    'WorkflowError',
    'SecurityError',
    # Enums
    'StageStatus',
    'SkillErrorType',
    'SkillWorkflowStepStatus',
    'IntentType',
    # Models
    'Skill',
    'SkillExecution',
    'SkillRequirement',
    'SkillBundle',
    'ConditionalBranch',
    'LoopConfig',
    'SkillStepConfig',
    'SkillStep',
    'SkillWorkflowTrigger',
    'SkillWorkflowConfig',
    'SkillWorkflow',
    'SkillWorkflowExecution',
    'Role',
    'QualityGate',
    'Output',
    'Stage',
    'Workflow',
    'ExecutionState',
    'ProjectContext',
    'AgentContext',
    'ContextSummary',
    'Task',
    'TaskAssignment',
    'Team',
    'Company',
    # Execution tracking
    'ExecutionTracker',
    # Skill selection
    'SkillSelector',
    'RetryHandler',
    # Condition evaluation
    'ConditionEvaluator',
    # Variable resolution
    'VariableResolver',
    # Remaining classes (from engine.py)
    'ProjectScanner',
    'SchemaLoader',
    'ConfigLoader',
    'RoleManager',
    'WorkflowExecutor',
    'StateStorage',
    'FileStateStorage',
    'TeamManager',
    'QualityGateSystem',
    'WorkflowEngine',
    'IntentRouter',
    'IntentAgent',
    'BugAnalysisAgent',
    'IntentHandler',
    'handle_user_input',
    'Agent',
    'SkillInvoker',
    'PlaceholderSkillInvoker',
    'LLMSkillInvoker',
    'CompositeSkillInvoker',
    'SkillWorkflowExecutor',
    'AgentOrchestrator',
    'RoleExecutor',
    'SkillBenchmark',
    'TaskRouter',
    'normalize_path',
]

