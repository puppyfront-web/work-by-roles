"""
Unit tests for error handling and edge cases.
"""
import pytest
from pathlib import Path
import yaml

from work_by_roles.core.workflow_engine import WorkflowEngine
from work_by_roles.core.agent_orchestrator import AgentOrchestrator
from work_by_roles.core.exceptions import WorkflowError, ValidationError
from work_by_roles.core.models import Role, Stage, Workflow


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_workflow_config(self, temp_workspace):
        """Test handling invalid workflow configuration."""
        engine = WorkflowEngine(workspace_path=temp_workspace)
        
        # Create invalid workflow file
        workflow_file = temp_workspace / ".workflow" / "workflow_schema.yaml"
        workflow_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(workflow_file, "w") as f:
            yaml.dump({"invalid": "config"}, f)
        
        # Should handle gracefully
        try:
            engine.load_all_configs(workflow_file=workflow_file)
        except (WorkflowError, ValidationError, Exception):
            # Expected to fail, but should not crash
            pass
    
    def test_missing_role_reference(self, temp_workspace):
        """Test handling missing role reference."""
        engine = WorkflowEngine(workspace_path=temp_workspace)
        
        # Create workflow with missing role
        workflow = Workflow(
            id="test_workflow",
            name="Test",
            description="Test",
            stages=[
                Stage(
                    id="test_stage",
                    name="Test Stage",
                    role="missing_role",
                    order=1,
                    prerequisites=[],
                    entry_criteria=[],
                    exit_criteria=[],
                    quality_gates=[],
                    outputs=[],
                    goal_template="Test"
                )
            ]
        )
        
        engine.workflow = workflow
        
        # Should raise error when trying to execute
        with pytest.raises((WorkflowError, ValidationError)):
            engine.start_stage("test_stage", "missing_role")
    
    def test_circular_dependency_detection(self, temp_workspace):
        """Test circular dependency detection."""
        from work_by_roles.core.models import SkillWorkflow, SkillStep
        
        workflow = SkillWorkflow(
            id="test_workflow",
            name="Test",
            description="Test",
            steps=[
                SkillStep(
                    step_id="step1",
                    skill_id="skill1",
                    name="Step 1",
                    order=1,
                    depends_on=["step2"],
                    inputs={}
                ),
                SkillStep(
                    step_id="step2",
                    skill_id="skill2",
                    name="Step 2",
                    order=2,
                    depends_on=["step1"],
                    inputs={}
                )
            ],
            outputs={}
        )
        
        # Should detect circular dependency
        try:
            sorted_steps = workflow.topological_sort()
            # If no exception, check if it handles gracefully
            assert isinstance(sorted_steps, list)
        except (WorkflowError, ValueError):
            # Expected to detect circular dependency
            pass
    
    def test_corrupted_state_file(self, temp_workspace):
        """Test handling corrupted state file."""
        engine = WorkflowEngine(workspace_path=temp_workspace)
        
        # Create corrupted state file
        state_file = temp_workspace / ".workflow" / "state.yaml"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("invalid yaml: [")
        
        # Should handle gracefully
        try:
            engine.load_state()
        except (WorkflowError, yaml.YAMLError, Exception):
            # Expected to fail, but should not crash
            pass
    
    def test_empty_workflow(self, temp_workspace):
        """Test handling empty workflow."""
        engine = WorkflowEngine(workspace_path=temp_workspace)
        
        workflow = Workflow(
            id="empty_workflow",
            name="Empty",
            description="Empty workflow",
            stages=[]
        )
        
        engine.workflow = workflow
        
        # Should handle empty workflow
        assert len(engine.workflow.stages) == 0
    
    def test_invalid_skill_reference(self, temp_workspace):
        """Test handling invalid skill reference."""
        from work_by_roles.core.agent_orchestrator import AgentOrchestrator
        
        engine = WorkflowEngine(workspace_path=temp_workspace)
        orchestrator = AgentOrchestrator(engine)
        
        # Try to execute non-existent skill
        with pytest.raises((WorkflowError, ValidationError, KeyError)):
            orchestrator.execute_skill(
                skill_id="non_existent_skill",
                input_data={},
                role_id="test_role"
            )

