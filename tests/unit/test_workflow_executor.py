"""
Unit tests for WorkflowExecutor.
"""
import pytest

from work_by_roles.core.workflow_executor import WorkflowExecutor
from work_by_roles.core.role_manager import RoleManager
from work_by_roles.core.enums import StageStatus


class TestWorkflowExecutor:
    """Test WorkflowExecutor functionality."""
    
    def test_executor_initialization(self, sample_workflow, sample_role):
        """Test initializing WorkflowExecutor."""
        role_manager = RoleManager()
        role_manager.roles = {"test_role": sample_role}
        executor = WorkflowExecutor(sample_workflow, role_manager)
        
        assert executor.workflow == sample_workflow
        assert executor.role_manager == role_manager
    
    def test_start_stage(self, sample_workflow, sample_role):
        """Test starting a stage."""
        role_manager = RoleManager()
        role_manager.roles = {"test_role": sample_role}
        executor = WorkflowExecutor(sample_workflow, role_manager)
        
        executor.start_stage("test_stage", "test_role")
        
        assert executor.state.current_stage == "test_stage"
        assert executor.state.current_role == "test_role"
        assert executor.state.stage_status["test_stage"] == StageStatus.IN_PROGRESS
    
    def test_complete_stage(self, sample_workflow, sample_role):
        """Test completing a stage."""
        role_manager = RoleManager()
        role_manager.roles = {"test_role": sample_role}
        executor = WorkflowExecutor(sample_workflow, role_manager)
        
        executor.start_stage("test_stage", "test_role")
        executor.complete_stage("test_stage")
        
        assert "test_stage" in executor.get_completed_stages()
        assert executor.state.stage_status["test_stage"] == StageStatus.COMPLETED
    
    def test_can_transition_to(self, sample_workflow, sample_role):
        """Test checking if can transition to a stage."""
        role_manager = RoleManager()
        role_manager.roles = {"test_role": sample_role}
        executor = WorkflowExecutor(sample_workflow, role_manager)
        
        # First stage should be transitionable
        can_transition, errors = executor.can_transition_to("test_stage")
        assert can_transition is True
        assert len(errors) == 0

