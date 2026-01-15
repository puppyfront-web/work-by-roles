"""
End-to-end tests for full workflow execution.
"""
import pytest
from pathlib import Path

from work_by_roles.core.workflow_engine import WorkflowEngine
from work_by_roles.core.agent_orchestrator import AgentOrchestrator


class TestFullWorkflow:
    """Test full workflow end-to-end."""
    
    def test_complete_workflow_from_init_to_completion(self, sample_workflow_config):
        """Test complete workflow from initialization to completion."""
        engine = WorkflowEngine(workspace_path=sample_workflow_config["workspace"])
        
        # Load configurations
        engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        # Verify workflow loaded
        assert engine.workflow is not None
        assert len(engine.workflow.stages) > 0
        
        # Start first stage
        first_stage = engine.workflow.stages[0]
        engine.start_stage(first_stage.id, first_stage.role)
        
        # Execute with orchestrator
        orchestrator = AgentOrchestrator(engine)
        result = orchestrator.execute_stage(first_stage.id, use_llm=False)
        
        assert result["stage"] == first_stage.id
        
        # Complete stage
        complete_result = orchestrator.complete_stage(first_stage.id)
        assert "quality_gates_passed" in complete_result
        
        # Verify state
        assert engine.executor is not None
        assert first_stage.id in engine.executor.get_completed_stages()

