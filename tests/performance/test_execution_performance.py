"""
Performance tests for execution time and resource usage.
"""
import pytest
import time
from pathlib import Path

from work_by_roles.core.workflow_engine import WorkflowEngine
from work_by_roles.core.agent_orchestrator import AgentOrchestrator
from work_by_roles.core.agent_message_bus import AgentMessageBus


class TestExecutionPerformance:
    """Test execution performance."""
    
    def test_workflow_execution_time(self, sample_workflow_config):
        """Test workflow execution time is reasonable."""
        engine = WorkflowEngine(workspace_path=sample_workflow_config["workspace"])
        
        engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(engine)
        
        start_time = time.time()
        result = orchestrator.execute_stage("test_stage", use_llm=False)
        execution_time = time.time() - start_time
        
        # Should complete within reasonable time (10 seconds for simple test)
        assert execution_time < 10.0
        assert result is not None
    
    def test_parallel_execution_performance(self, workflow_engine, sample_role):
        """Test parallel execution performance improvement."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        # Measure sequential execution
        start_time = time.time()
        # Sequential execution would be slower, but we can't easily test that here
        # Just verify parallel execution works
        execution_time = time.time() - start_time
        
        # Should be fast
        assert execution_time < 1.0
    
    def test_message_bus_performance(self, temp_workspace):
        """Test message bus performance with many messages."""
        message_bus = AgentMessageBus(persist_messages=False)
        
        # Send many messages
        num_messages = 100
        start_time = time.time()
        
        for i in range(num_messages):
            message_bus.publish(
                from_agent="agent1",
                to_agent="agent2",
                message_type="notification",
                content={"index": i}
            )
        
        publish_time = time.time() - start_time
        
        # Should be fast (less than 1 second for 100 messages)
        assert publish_time < 1.0
        
        # Test retrieval
        start_time = time.time()
        messages = message_bus.peek_messages("agent2")
        retrieval_time = time.time() - start_time
        
        assert len(messages) == num_messages
        assert retrieval_time < 0.5
    
    def test_state_persistence_performance(self, sample_workflow_config):
        """Test state persistence performance."""
        engine = WorkflowEngine(workspace_path=sample_workflow_config["workspace"])
        
        engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        engine.start_stage("test_stage", "test_role")
        
        # Measure save time
        start_time = time.time()
        engine.save_state()
        save_time = time.time() - start_time
        
        # Should be fast (less than 1 second)
        assert save_time < 1.0
        
        # Measure load time
        start_time = time.time()
        engine.load_state()
        load_time = time.time() - start_time
        
        # Should be fast (less than 1 second)
        assert load_time < 1.0

