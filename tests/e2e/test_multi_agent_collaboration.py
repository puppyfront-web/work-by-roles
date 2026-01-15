"""
End-to-end tests for multi-agent collaboration.
"""
import pytest

from work_by_roles.core.workflow_engine import WorkflowEngine
from work_by_roles.core.agent_orchestrator import AgentOrchestrator


class TestMultiAgentCollaboration:
    """Test multi-agent collaboration end-to-end."""
    
    def test_collaboration_workflow(self, workflow_engine, sample_role):
        """Test complete collaboration workflow."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        goal = "实现完整的用户认证系统"
        result = orchestrator.execute_with_collaboration(
            goal=goal,
            role_ids=["test_role"],
            use_llm=False
        )
        
        # Verify collaboration result structure
        assert result["goal"] == goal
        assert "decomposition" in result
        assert "agents" in result
        assert "task_results" in result
        assert "collaboration_summary" in result
        
        # Verify decomposition
        decomposition = result["decomposition"]
        assert len(decomposition.tasks) > 0
        assert len(decomposition.execution_order) > 0
        
        # Verify agents were created
        assert len(result["agents"]) > 0
        
        # Verify summary
        summary = result["collaboration_summary"]
        assert summary["total_tasks"] > 0
        assert "completed_tasks" in summary
        assert "active_agents" in summary

