"""
Workflow executor for executing workflow stages.
Following Single Responsibility Principle - handles workflow stage execution only.
"""

from typing import Dict, List, Optional, Set, Tuple

from .exceptions import ValidationError, WorkflowError
from .enums import StageStatus
from .models import Workflow, Stage, ExecutionState
from .role_manager import RoleManager


class WorkflowExecutor:
    """Executes workflow stages"""
    
    def __init__(self, workflow: Workflow, role_manager: RoleManager):
        self.workflow = workflow
        self.role_manager = role_manager
        self.state = ExecutionState()
        self._validate_workflow()
    
    def _validate_workflow(self) -> None:
        """Validate workflow structure"""
        stage_ids = set()
        orders = []
        
        for stage in self.workflow.stages:
            # Check unique stage IDs
            if stage.id in stage_ids:
                raise ValidationError(f"Duplicate stage ID: {stage.id}")
            stage_ids.add(stage.id)
            orders.append(stage.order)
            
            # Validate role exists
            if not self.role_manager.validate_role_exists(stage.role):
                raise ValidationError(
                    f"Role '{stage.role}' not found for stage '{stage.id}'",
                    field="role",
                    value=stage.role,
                    context={"stage_id": stage.id, "stage_name": stage.name}
                )
            
            # Validate prerequisites
            for prereq in stage.prerequisites:
                if prereq not in stage_ids:
                    raise ValidationError(f"Prerequisite '{prereq}' not found for stage '{stage.id}'")
        
        # Validate sequential ordering
        orders.sort()
        expected_orders = list(range(1, len(orders) + 1))
        if orders != expected_orders:
            raise ValidationError(f"Stage orders must be sequential starting from 1")
    
    def get_current_stage(self) -> Optional[Stage]:
        """Get current stage"""
        if self.state.current_stage:
            return self._get_stage_by_id(self.state.current_stage)
        return None
    
    def _get_stage_by_id(self, stage_id: str) -> Optional[Stage]:
        """Get stage by ID"""
        for stage in self.workflow.stages:
            if stage.id == stage_id:
                return stage
        return None
    
    def can_transition_to(self, stage_id: str) -> Tuple[bool, List[str]]:
        """Check if transition to stage is allowed"""
        stage = self._get_stage_by_id(stage_id)
        if not stage:
            return False, [f"Stage '{stage_id}' not found"]
        
        errors = []
        
        # Check prerequisites
        for prereq in stage.prerequisites:
            if prereq not in self.state.completed_stages:
                errors.append(f"Prerequisite stage '{prereq}' not completed")
        
        # Check if previous stages are completed
        for s in self.workflow.stages:
            if s.order < stage.order and s.id not in self.state.completed_stages:
                errors.append(f"Previous stage '{s.id}' (order {s.order}) not completed")
        
        return len(errors) == 0, errors
    
    def start_stage(self, stage_id: str, role_id: str) -> None:
        """Start a stage"""
        stage = self._get_stage_by_id(stage_id)
        if not stage:
            raise WorkflowError(f"Stage '{stage_id}' not found")
        
        # Validate role matches stage role
        if stage.role != role_id:
            raise WorkflowError(
                f"Role '{role_id}' does not match required role '{stage.role}' for stage '{stage_id}'",
                stage_id=stage_id,
                role_id=role_id,
                context={"required_role": stage.role, "stage_name": stage.name}
            )
        
        # Check if transition is allowed
        can_transition, errors = self.can_transition_to(stage_id)
        if not can_transition:
            raise WorkflowError(
                f"Cannot transition to stage '{stage_id}': {', '.join(errors)}",
                stage_id=stage_id,
                role_id=role_id,
                context={"errors": errors, "prerequisites": stage.prerequisites if stage else []}
            )
        
        self.state.current_stage = stage_id
        self.state.current_role = role_id
        self.state.stage_status[stage_id] = StageStatus.IN_PROGRESS
    
    def complete_stage(self, stage_id: str) -> None:
        """Mark stage as completed"""
        if stage_id not in self.state.stage_status:
            raise WorkflowError(f"Stage '{stage_id}' not started")
        
        self.state.stage_status[stage_id] = StageStatus.COMPLETED
        self.state.completed_stages.add(stage_id)
        
        # Clear current stage if it's the one being completed
        if self.state.current_stage == stage_id:
            self.state.current_stage = None
            self.state.current_role = None
    
    def get_stage_status(self, stage_id: str) -> Optional[StageStatus]:
        """Get status of a stage"""
        if self.state.current_stage == stage_id:
            return StageStatus.IN_PROGRESS
        if stage_id in self.state.completed_stages:
            return StageStatus.COMPLETED
        if stage_id in self.state.stage_status:
            return self.state.stage_status[stage_id]
        return StageStatus.PENDING
    
    def get_completed_stages(self) -> Set[str]:
        """Get set of completed stage IDs"""
        return self.state.completed_stages.copy()
    
    def reset_state(self) -> None:
        """Reset execution state to initial state (all stages reset to PENDING)"""
        self.state = ExecutionState()

