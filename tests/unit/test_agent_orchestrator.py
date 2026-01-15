"""
Unit tests for AgentOrchestrator.
"""
import pytest
import asyncio

from work_by_roles.core.agent_orchestrator import AgentOrchestrator
from work_by_roles.core.exceptions import WorkflowError


class TestAgentOrchestrator:
    """Test AgentOrchestrator functionality."""
    
    def test_orchestrator_initialization(self, workflow_engine):
        """Test initializing AgentOrchestrator."""
        orchestrator = AgentOrchestrator(workflow_engine)
        
        assert orchestrator.engine == workflow_engine
        assert orchestrator.message_bus is not None
        assert orchestrator.task_decomposer is not None
    
    def test_orchestrator_initialization_with_message_bus(self, workflow_engine, message_bus):
        """Test initializing with custom message bus."""
        orchestrator = AgentOrchestrator(workflow_engine, message_bus=message_bus)
        
        assert orchestrator.message_bus == message_bus
    
    def test_execute_stage_constraints_only(self, workflow_engine, sample_workflow_config):
        """Test executing stage with constraints only."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        result = orchestrator.execute_stage("test_stage", use_llm=False)
        
        assert result["stage"] == "test_stage"
        assert "agent" in result
        assert result["status"] == "constraints_checked"
        assert result["llm_used"] is False
    
    def test_execute_stage_with_llm(self, workflow_engine, sample_workflow_config):
        """Test executing stage with LLM (if available)."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        # Without LLM client, should fall back to constraints only
        result = orchestrator.execute_stage("test_stage", use_llm=True)
        
        # Should still work but without LLM
        assert result["stage"] == "test_stage"
    
    def test_execute_parallel_stages_sync(self, workflow_engine, sample_workflow_config):
        """Test synchronous parallel stage execution."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        # Execute single stage (no real parallelism, but tests the method)
        results = orchestrator.execute_parallel_stages_sync(
            stage_ids=["test_stage"],
            use_llm=False
        )
        
        assert "test_stage" in results
        assert results["test_stage"]["stage"] == "test_stage"
    
    @pytest.mark.asyncio
    async def test_execute_parallel_stages_async(self, workflow_engine, sample_workflow_config):
        """Test asynchronous parallel stage execution."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        results = await orchestrator.execute_parallel_stages(
            stage_ids=["test_stage"],
            use_llm=False
        )
        
        assert "test_stage" in results
        assert results["test_stage"]["stage"] == "test_stage"
    
    def test_execute_with_collaboration(self, workflow_engine, sample_workflow_config):
        """Test collaborative execution."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        goal = "实现测试功能"
        result = orchestrator.execute_with_collaboration(
            goal=goal,
            use_llm=False
        )
        
        assert result["goal"] == goal
        assert "decomposition" in result
        assert "agents" in result
        assert "task_results" in result
        assert "collaboration_summary" in result
    
    def test_execute_with_collaboration_specific_roles(self, workflow_engine, sample_workflow_config):
        """Test collaborative execution with specific roles."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        goal = "完成任务"
        result = orchestrator.execute_with_collaboration(
            goal=goal,
            role_ids=["test_role"],
            use_llm=False
        )
        
        assert result["goal"] == goal
        assert len(result["agents"]) > 0
    
    def test_create_agent_pool(self, workflow_engine, sample_role):
        """Test creating agent pool."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        agents = orchestrator._create_agent_pool([sample_role])
        
        assert len(agents) == 1
        assert isinstance(agents, dict)
        for agent_id, agent in agents.items():
            assert agent.role == sample_role
            assert agent.message_bus == orchestrator.message_bus
    
    @pytest.mark.asyncio
    async def test_wait_for_dependencies(self, workflow_engine):
        """Test waiting for dependencies."""
        orchestrator = AgentOrchestrator(workflow_engine)
        
        completed = {"task1"}
        
        # Task with satisfied dependencies
        await orchestrator._wait_for_dependencies("task2", ["task1"], completed)
        # Should complete immediately
        
        # Task with unsatisfied dependencies
        import asyncio
        completed.remove("task1")
        
        # Start waiting task
        wait_task = asyncio.create_task(
            orchestrator._wait_for_dependencies("task2", ["task1"], completed)
        )
        
        # Complete dependency after short delay
        await asyncio.sleep(0.1)
        completed.add("task1")
        
        # Wait should complete
        await asyncio.wait_for(wait_task, timeout=1.0)
    
    def test_execute_skill(self, workflow_engine, sample_workflow_config):
        """Test executing a skill."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        # Execute skill
        result = orchestrator.execute_skill(
            skill_id="test_skill",
            input_data={"input": "test"},
            stage_id="test_stage",
            role_id="test_role"
        )
        
        # Should return a result (may be placeholder)
        assert result is not None
    
    def test_execute_skill_not_found(self, workflow_engine):
        """Test executing non-existent skill raises error."""
        orchestrator = AgentOrchestrator(workflow_engine)
        
        with pytest.raises(WorkflowError):
            orchestrator.execute_skill("nonexistent_skill", {})
    
    def test_complete_stage(self, workflow_engine, sample_workflow_config):
        """Test completing a stage."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        # Start stage first
        workflow_engine.start_stage("test_stage", "test_role")
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        result = orchestrator.complete_stage("test_stage")
        
        assert "stage" in result
        assert "quality_gates_passed" in result
    
    def test_get_execution_summary(self, workflow_engine, sample_workflow_config):
        """Test getting execution summary."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(workflow_engine)
        orchestrator.execute_stage("test_stage", use_llm=False)
        
        summary = orchestrator.get_execution_summary()
        
        assert "total_stages_executed" in summary
        assert "agents_used" in summary
        assert "log" in summary
        assert summary["total_stages_executed"] > 0

