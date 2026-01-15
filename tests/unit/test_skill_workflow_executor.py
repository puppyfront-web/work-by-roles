"""
Unit tests for SkillWorkflowExecutor.
"""
import pytest

from work_by_roles.core.skill_workflow_executor import SkillWorkflowExecutor
from work_by_roles.core.models import SkillWorkflow, SkillStep
from work_by_roles.core.enums import SkillWorkflowStepStatus


class TestSkillWorkflowExecutor:
    """Test SkillWorkflowExecutor functionality."""
    
    def test_executor_initialization(self, workflow_engine):
        """Test initializing SkillWorkflowExecutor."""
        from work_by_roles.core.skill_invoker import PlaceholderSkillInvoker
        from work_by_roles.core.execution_tracker import ExecutionTracker
        
        invoker = PlaceholderSkillInvoker()
        tracker = ExecutionTracker()
        executor = SkillWorkflowExecutor(workflow_engine, invoker, tracker)
        
        assert executor.engine == workflow_engine
        assert executor.skill_invoker == invoker
        assert executor.execution_tracker == tracker
    
    def test_execute_workflow_simple(self, workflow_engine, sample_skill):
        """Test executing a simple workflow."""
        from work_by_roles.core.skill_invoker import PlaceholderSkillInvoker
        from work_by_roles.core.execution_tracker import ExecutionTracker
        
        workflow_engine.role_manager.skill_library = {"test_skill": sample_skill}
        
        # Create a simple workflow
        workflow = SkillWorkflow(
            id="test_workflow",
            name="Test Workflow",
            description="A test workflow",
            steps=[
                SkillStep(
                    step_id="step1",
                    skill_id="test_skill",
                    name="Step 1",
                    order=1,
                    depends_on=[],
                    inputs={"input": "test"}
                )
            ],
            outputs={}
        )
        
        workflow_engine.role_manager.skill_workflows = {"test_workflow": workflow}
        
        invoker = PlaceholderSkillInvoker()
        tracker = ExecutionTracker()
        executor = SkillWorkflowExecutor(workflow_engine, invoker, tracker)
        
        result = executor.execute_workflow(
            workflow_id="test_workflow",
            inputs={}
        )
        
        assert result.workflow_id == "test_workflow"
        assert result.status in ["completed", "running", "failed"]

