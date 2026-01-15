"""
Integration tests for workflow execution.
"""
import pytest
from pathlib import Path

from work_by_roles.core.workflow_engine import WorkflowEngine
from work_by_roles.core.agent_orchestrator import AgentOrchestrator


class TestWorkflowIntegration:
    """Test workflow integration."""
    
    def test_full_workflow_execution(self, sample_workflow_config):
        """Test executing a full workflow."""
        engine = WorkflowEngine(workspace_path=sample_workflow_config["workspace"])
        
        engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        # Start stage
        engine.start_stage("test_stage", "test_role")
        
        # Execute with orchestrator
        orchestrator = AgentOrchestrator(engine)
        result = orchestrator.execute_stage("test_stage", use_llm=False)
        
        assert result["stage"] == "test_stage"
        assert result["status"] == "constraints_checked"
        
        # Complete stage
        complete_result = orchestrator.complete_stage("test_stage")
        assert "quality_gates_passed" in complete_result
    
    def test_state_persistence(self, sample_workflow_config):
        """Test state persistence and recovery."""
        workspace = sample_workflow_config["workspace"]
        engine1 = WorkflowEngine(workspace_path=workspace)
        
        engine1.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        # Start stage and save state
        engine1.start_stage("test_stage", "test_role")
        engine1.save_state()
        
        # Create new engine and load state
        engine2 = WorkflowEngine(workspace_path=workspace)
        engine2.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        engine2.load_state()
        
        # Verify state was restored
        assert engine2.executor is not None
        assert engine2.executor.state.current_stage == "test_stage"

