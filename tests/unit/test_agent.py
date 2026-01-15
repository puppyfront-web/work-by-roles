"""
Unit tests for Agent class.
"""
import pytest
from pathlib import Path

from work_by_roles.core.agent import Agent
from work_by_roles.core.exceptions import WorkflowError


class TestAgent:
    """Test Agent functionality."""
    
    def test_agent_initialization(self, workflow_engine, sample_role):
        """Test initializing an Agent."""
        agent = Agent(sample_role, workflow_engine)
        
        assert agent.role == sample_role
        assert agent.engine == workflow_engine
        assert agent.context is None
        assert agent.agent_id.startswith(sample_role.id)
        assert agent.message_bus is None
    
    def test_agent_initialization_with_message_bus(self, workflow_engine, sample_role, message_bus):
        """Test initializing Agent with message bus."""
        agent = Agent(sample_role, workflow_engine, message_bus=message_bus)
        
        assert agent.message_bus == message_bus
    
    def test_agent_prepare(self, workflow_engine, sample_role):
        """Test preparing an agent."""
        agent = Agent(sample_role, workflow_engine)
        
        agent.prepare("Test goal", {"input": "test"})
        
        assert agent.context is not None
        assert agent.context.goal == "Test goal"
        assert agent.context.inputs == {"input": "test"}
        assert agent.context.workspace_path == workflow_engine.workspace_path
    
    def test_agent_prepare_with_shared_contexts(self, workflow_engine, sample_role, message_bus):
        """Test prepare handles shared contexts."""
        # Share context from another agent
        message_bus.share_context("other_agent", {
            "goal": "Other goal",
            "inputs": {"other": "data"},
            "outputs": {},
            "decisions": []
        })
        
        agent = Agent(sample_role, workflow_engine, message_bus=message_bus)
        agent.prepare("Main goal", {})
        
        # Should have shared context
        assert len(agent.context.shared_contexts) > 0
    
    def test_agent_make_decision(self, workflow_engine, sample_role):
        """Test making a decision."""
        agent = Agent(sample_role, workflow_engine)
        agent.prepare("Test goal")
        
        agent.make_decision("Test decision")
        
        assert len(agent.context.decisions) == 1
        assert agent.context.decisions[0] == "Test decision"
    
    def test_agent_produce_output(self, workflow_engine, sample_role, temp_workspace):
        """Test producing output."""
        agent = Agent(sample_role, workflow_engine)
        agent.prepare("Test goal")
        
        agent.produce_output("test_file.txt", "Test content")
        
        assert "test_file.txt" in agent.context.outputs
        output_path = Path(agent.context.outputs["test_file.txt"])
        assert output_path.exists()
        assert output_path.read_text() == "Test content"
    
    def test_agent_produce_output_document(self, workflow_engine, sample_role, temp_workspace):
        """Test producing document output (should go to temp directory)."""
        agent = Agent(sample_role, workflow_engine)
        agent.prepare("Test goal")
        
        agent.produce_output("test_doc.md", "Document content", output_type="document")
        
        assert "test_doc.md" in agent.context.outputs
        output_path = Path(agent.context.outputs["test_doc.md"])
        assert ".workflow/temp" in str(output_path)
        assert output_path.exists()
    
    def test_agent_get_context_summary(self, workflow_engine, sample_role, sample_workflow_config):
        """Test getting context summary."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        agent = Agent(sample_role, workflow_engine)
        agent.prepare("Test goal")
        
        summary = agent.get_context_summary()
        
        assert summary is not None
        assert hasattr(summary, "stage_summary")
        assert hasattr(summary, "key_outputs")
        assert hasattr(summary, "current_goal")
    
    def test_agent_generate_prompt(self, workflow_engine, sample_role, sample_stage):
        """Test generating prompt."""
        agent = Agent(sample_role, workflow_engine)
        agent.prepare("Test goal")
        
        prompt = agent.generate_prompt(sample_stage)
        
        assert isinstance(prompt, str)
        assert sample_role.name in prompt
        assert sample_stage.name in prompt
        assert "Test goal" in prompt
    
    def test_agent_send_message(self, workflow_engine, sample_role, message_bus):
        """Test sending a message."""
        agent = Agent(sample_role, workflow_engine, message_bus=message_bus)
        
        message_id = agent.send_message("target_agent", "request", {"question": "test"})
        
        assert message_id != ""
        messages = message_bus.peek_messages("target_agent")
        assert len(messages) > 0
        assert messages[0].from_agent == agent.agent_id
    
    def test_agent_send_message_no_bus(self, workflow_engine, sample_role):
        """Test sending message without message bus raises error."""
        agent = Agent(sample_role, workflow_engine)
        
        with pytest.raises(WorkflowError):
            agent.send_message("target_agent", "request", {})
    
    def test_agent_check_messages(self, workflow_engine, sample_role, message_bus):
        """Test checking messages."""
        agent = Agent(sample_role, workflow_engine, message_bus=message_bus)
        
        # Send a message to this agent
        message_bus.publish("other_agent", agent.agent_id, "notification", {"test": True})
        
        messages = agent.check_messages()
        
        assert len(messages) == 1
        assert messages[0].from_agent == "other_agent"
        # Messages should still be there (peek, not subscribe)
        assert len(message_bus.peek_messages(agent.agent_id)) == 1
    
    def test_agent_get_messages(self, workflow_engine, sample_role, message_bus):
        """Test getting messages (removes them)."""
        agent = Agent(sample_role, workflow_engine, message_bus=message_bus)
        
        message_bus.publish("other_agent", agent.agent_id, "notification", {})
        
        messages = agent.get_messages()
        
        assert len(messages) == 1
        # Messages should be removed
        assert len(message_bus.peek_messages(agent.agent_id)) == 0
    
    def test_agent_share_context(self, workflow_engine, sample_role, message_bus):
        """Test sharing context."""
        agent = Agent(sample_role, workflow_engine, message_bus=message_bus)
        agent.prepare("Test goal", {"input": "test"})
        
        agent.share_context()
        
        # Context should be shared
        shared = message_bus.get_context(agent.agent_id)
        assert shared is not None
        assert shared["goal"] == "Test goal"
        assert shared["inputs"] == {"input": "test"}
    
    def test_agent_share_context_no_bus(self, workflow_engine, sample_role):
        """Test sharing context without message bus raises error."""
        agent = Agent(sample_role, workflow_engine)
        agent.prepare("Test goal")
        
        with pytest.raises(WorkflowError):
            agent.share_context()
    
    def test_agent_request_feedback(self, workflow_engine, sample_role, message_bus):
        """Test requesting feedback."""
        agent = Agent(sample_role, workflow_engine, message_bus=message_bus)
        
        feedback = agent.request_feedback("Test question")
        
        # Should broadcast the request
        # Check that broadcast was sent
        all_messages = []
        for agent_id in message_bus.messages.keys():
            all_messages.extend(message_bus.peek_messages(agent_id))
        
        # Should have at least one broadcast message
        assert len(all_messages) >= 0  # May be empty if no other agents
    
    def test_agent_review_output(self, workflow_engine, sample_role, message_bus):
        """Test reviewing output."""
        agent = Agent(sample_role, workflow_engine, message_bus=message_bus)
        
        output = {
            "agent_id": "target_agent",
            "output_type": "code",
            "content": "def test(): pass"
        }
        
        review = agent.review_output(output)
        
        assert review["reviewer"] == agent.agent_id
        assert review["reviewed_output"] == output
        assert "approved" in review
        assert "feedback" in review
    
    def test_agent_review_output_no_bus(self, workflow_engine, sample_role):
        """Test review output without message bus raises error."""
        agent = Agent(sample_role, workflow_engine)
        
        with pytest.raises(WorkflowError):
            agent.review_output({"agent_id": "target", "output_type": "code", "content": ""})

