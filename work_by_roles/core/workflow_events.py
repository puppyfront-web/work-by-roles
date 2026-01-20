"""
Workflow event logging system for observability and replay.
Following Single Responsibility Principle - handles workflow event logging only.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import yaml
import hashlib


@dataclass
class WorkflowEvent:
    """
    A single workflow execution event.
    
    Represents a point-in-time snapshot of workflow execution state,
    including stage, role, skill, input/output references, and status.
    """
    workflow_id: str
    stage: Optional[str] = None
    role: Optional[str] = None
    skill: Optional[str] = None
    input_hash: Optional[str] = None  # Hash of input data for deduplication
    output_ref: Optional[str] = None  # Reference to output (file path or ID)
    status: str = "pending"  # "success" | "failed" | "retry" | "pending" | "skipped"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "workflow_id": self.workflow_id,
            "stage": self.stage,
            "role": self.role,
            "skill": self.skill,
            "input_hash": self.input_hash,
            "output_ref": self.output_ref,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "error": self.error,
            "execution_time": self.execution_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowEvent':
        """Create from dictionary"""
        return cls(
            workflow_id=data["workflow_id"],
            stage=data.get("stage"),
            role=data.get("role"),
            skill=data.get("skill"),
            input_hash=data.get("input_hash"),
            output_ref=data.get("output_ref"),
            status=data.get("status", "pending"),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
            error=data.get("error"),
            execution_time=data.get("execution_time", 0.0)
        )
    
    @staticmethod
    def hash_input(input_data: Dict[str, Any]) -> str:
        """Generate hash for input data"""
        input_str = json.dumps(input_data, sort_keys=True, default=str)
        return hashlib.sha256(input_str.encode()).hexdigest()[:16]


class EventLogger:
    """
    Logger for workflow events.
    
    Provides methods to record, query, and export workflow execution events.
    """
    
    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize event logger.
        
        Args:
            log_file: Optional path to persistent log file
        """
        self.events: List[WorkflowEvent] = []
        self.log_file = log_file
        if log_file and log_file.exists():
            self._load_from_file()
    
    def log_event(self, event: WorkflowEvent) -> None:
        """Record a workflow event"""
        self.events.append(event)
        if self.log_file:
            self._append_to_file(event)
    
    def log_skill_execution(
        self,
        workflow_id: str,
        skill_id: str,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]] = None,
        status: str = "success",
        stage_id: Optional[str] = None,
        role_id: Optional[str] = None,
        error: Optional[str] = None,
        execution_time: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> WorkflowEvent:
        """
        Log a skill execution event.
        
        Args:
            workflow_id: Workflow ID
            skill_id: Skill ID that was executed
            input_data: Input data for the skill
            output_data: Output data (optional)
            status: Execution status
            stage_id: Stage ID (optional)
            role_id: Role ID (optional)
            error: Error message if failed (optional)
            execution_time: Execution time in seconds
            metadata: Additional metadata
        
        Returns:
            Created WorkflowEvent
        """
        input_hash = WorkflowEvent.hash_input(input_data)
        output_ref = None
        
        # Generate output reference if output provided
        if output_data:
            output_hash = WorkflowEvent.hash_input(output_data)
            output_ref = f"{skill_id}_output_{output_hash[:8]}"
        
        event = WorkflowEvent(
            workflow_id=workflow_id,
            stage=stage_id,
            role=role_id,
            skill=skill_id,
            input_hash=input_hash,
            output_ref=output_ref,
            status=status,
            error=error,
            execution_time=execution_time,
            metadata=metadata or {}
        )
        
        self.log_event(event)
        return event
    
    def log_stage_transition(
        self,
        workflow_id: str,
        stage_id: str,
        role_id: str,
        status: str = "in_progress",
        metadata: Optional[Dict[str, Any]] = None
    ) -> WorkflowEvent:
        """
        Log a stage transition event.
        
        Args:
            workflow_id: Workflow ID
            stage_id: Stage ID
            role_id: Role ID
            status: Stage status
            metadata: Additional metadata
        
        Returns:
            Created WorkflowEvent
        """
        event = WorkflowEvent(
            workflow_id=workflow_id,
            stage=stage_id,
            role=role_id,
            status=status,
            metadata=metadata or {}
        )
        
        self.log_event(event)
        return event
    
    def get_events(
        self,
        workflow_id: Optional[str] = None,
        stage: Optional[str] = None,
        role: Optional[str] = None,
        skill: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[WorkflowEvent]:
        """
        Query events with filters.
        
        Args:
            workflow_id: Filter by workflow ID
            stage: Filter by stage
            role: Filter by role
            skill: Filter by skill
            status: Filter by status
        
        Returns:
            List of matching events
        """
        filtered = self.events
        
        if workflow_id:
            filtered = [e for e in filtered if e.workflow_id == workflow_id]
        if stage:
            filtered = [e for e in filtered if e.stage == stage]
        if role:
            filtered = [e for e in filtered if e.role == role]
        if skill:
            filtered = [e for e in filtered if e.skill == skill]
        if status:
            filtered = [e for e in filtered if e.status == status]
        
        return filtered
    
    def get_workflow_events(self, workflow_id: str) -> List[WorkflowEvent]:
        """Get all events for a specific workflow"""
        return self.get_events(workflow_id=workflow_id)
    
    def export_events(
        self,
        output_file: Path,
        format: str = "json",
        filters: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Export events to file.
        
        Args:
            output_file: Output file path
            format: Export format ("json" or "yaml")
            filters: Optional filters dict (workflow_id, stage, role, skill, status)
        """
        events_to_export = self.events
        if filters:
            events_to_export = self.get_events(**filters)
        
        events_dict = [e.to_dict() for e in events_to_export]
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            with output_file.open('w', encoding='utf-8') as f:
                json.dump(events_dict, f, indent=2, ensure_ascii=False, default=str)
        elif format == "yaml":
            with output_file.open('w', encoding='utf-8') as f:
                yaml.dump(events_dict, f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _load_from_file(self) -> None:
        """Load events from log file"""
        if not self.log_file or not self.log_file.exists():
            return
        
        try:
            with self.log_file.open('r', encoding='utf-8') as f:
                if self.log_file.suffix in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
                
                if isinstance(data, list):
                    self.events = [WorkflowEvent.from_dict(e) for e in data]
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to load events from {self.log_file}: {e}")
    
    def _append_to_file(self, event: WorkflowEvent) -> None:
        """Append event to log file"""
        if not self.log_file:
            return
        
        try:
            # Load existing events
            existing_events = []
            if self.log_file.exists():
                with self.log_file.open('r', encoding='utf-8') as f:
                    if self.log_file.suffix in ['.yaml', '.yml']:
                        existing_events = yaml.safe_load(f) or []
                    else:
                        existing_events = json.load(f) or []
            
            # Append new event
            existing_events.append(event.to_dict())
            
            # Write back
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with self.log_file.open('w', encoding='utf-8') as f:
                if self.log_file.suffix in ['.yaml', '.yml']:
                    yaml.dump(existing_events, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(existing_events, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to append event to {self.log_file}: {e}")

