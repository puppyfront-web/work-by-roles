"""
Enumeration classes for the workflow engine.
"""

from enum import Enum


class StageStatus(Enum):
    """Stage execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class SkillErrorType(Enum):
    """Types of errors that can occur during skill execution"""
    VALIDATION_ERROR = "validation_error"  # Input validation failed
    EXECUTION_ERROR = "execution_error"    # Execution failed
    TIMEOUT_ERROR = "timeout_error"         # Timeout
    TEST_FAILURE = "test_failure"           # Test failure
    INSUFFICIENT_CONTEXT = "insufficient_context"  # Insufficient context


class SkillWorkflowStepStatus(Enum):
    """Status of a skill workflow step"""
    PENDING = "pending"
    READY = "ready"       # Dependencies met, ready to execute
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class IntentType(Enum):
    """User intent types"""
    FEATURE_REQUEST = "feature_request"  # 需求实现
    BUG_FIX = "bug_fix"                   # Bug修复
    QUERY = "query"                       # 查询/询问
    UNKNOWN = "unknown"                   # 未知意图

