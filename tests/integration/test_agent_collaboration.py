"""
Integration tests for agent collaboration.
"""
import pytest

from work_by_roles.core.workflow_engine import WorkflowEngine
from work_by_roles.core.agent_orchestrator import AgentOrchestrator
from work_by_roles.core.agent_message_bus import AgentMessageBus


class TestAgentCollaboration:
    """Test agent collaboration integration."""
    
    def test_multi_agent_message_passing(self, workflow_engine, sample_role):
        """Test message passing between multiple agents."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        # Create agents
        agents = orchestrator._create_agent_pool([sample_role])
        agent1 = list(agents.values())[0]
        
        # Send message
        message_id = agent1.send_message(
            to_agent="agent2",
            message_type="request",
            content={"question": "test"}
        )
        
        assert message_id != ""
        
        # Check message was received
        messages = orchestrator.message_bus.peek_messages("agent2")
        assert len(messages) > 0
    
    def test_task_decomposition_and_execution(self, workflow_engine, sample_role):
        """Test task decomposition and collaborative execution."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        goal = "实现测试功能"
        result = orchestrator.execute_with_collaboration(
            goal=goal,
            role_ids=["test_role"],
            use_llm=False
        )
        
        assert result["goal"] == goal
        assert "decomposition" in result
        assert len(result["decomposition"].tasks) > 0
        assert len(result["agents"]) > 0
    
    def test_context_sharing(self, workflow_engine, sample_role):
        """Test context sharing between agents."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        orchestrator = AgentOrchestrator(workflow_engine)
        agents = orchestrator._create_agent_pool([sample_role])
        
        agent1 = list(agents.values())[0]
        agent1.prepare("Test goal", {"input": "test"})
        agent1.share_context()
        
        # Another agent should be able to access shared context
        agent2 = list(agents.values())[0] if len(agents) > 1 else agent1
        agent2.prepare("Other goal", {})
        
        # Check shared context
        shared = orchestrator.message_bus.get_context(agent1.agent_id)
        assert shared is not None
        assert shared["goal"] == "Test goal"

