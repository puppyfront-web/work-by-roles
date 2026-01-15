"""
Exception classes for the workflow engine.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any


@dataclass
class ValidationError(Exception):
    """
    Enhanced validation error with context information.
    
    Maintains backward compatibility with string-based exception handling.
    """
    message: str
    field: Optional[str] = None
    value: Any = None
    context: Optional[Dict[str, Any]] = None
    
    def __init__(self, message: str, field: Optional[str] = None, 
                 value: Any = None, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.field = field
        self.value = value
        self.context = context or {}
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format error message with context"""
        parts = [self.message]
        if self.field:
            parts.append(f"Field: {self.field}")
        if self.value is not None:
            parts.append(f"Value: {repr(self.value)}")
        if self.context:
            ctx_parts = [f"{k}={v}" for k, v in self.context.items()]
            parts.append(f"Context: {', '.join(ctx_parts)}")
        return " | ".join(parts)
    
    def __str__(self) -> str:
        return self._format_message()


@dataclass
class WorkflowError(Exception):
    """
    Enhanced workflow error with stage and role context.
    
    Maintains backward compatibility with string-based exception handling.
    """
    message: str
    stage_id: Optional[str] = None
    role_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    
    def __init__(self, message: str, stage_id: Optional[str] = None,
                 role_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.stage_id = stage_id
        self.role_id = role_id
        self.context = context or {}
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format error message with context"""
        parts = [self.message]
        if self.stage_id:
            parts.append(f"Stage: {self.stage_id}")
        if self.role_id:
            parts.append(f"Role: {self.role_id}")
        if self.context:
            ctx_parts = [f"{k}={v}" for k, v in self.context.items()]
            parts.append(f"Context: {', '.join(ctx_parts)}")
        return " | ".join(parts)
    
    def __str__(self) -> str:
        return self._format_message()


class SecurityError(Exception):
    """Security-related error for path validation"""
    pass

