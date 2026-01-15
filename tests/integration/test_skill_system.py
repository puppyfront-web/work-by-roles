"""
Integration tests for skill system.
"""
import pytest

from work_by_roles.core.workflow_engine import WorkflowEngine
from work_by_roles.core.agent_orchestrator import AgentOrchestrator
from work_by_roles.core.skill_benchmark import SkillBenchmark


class TestSkillSystem:
    """Test skill system integration."""
    
    def test_skill_selection_and_execution(self, workflow_engine, sample_skill, sample_role, sample_workflow_config):
        """Test skill selection and execution flow."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(workflow_engine)
        
        # Select skill
        selected = orchestrator.skill_selector.select_skill("test task", sample_role)
        
        # May be None if no matching skill, which is OK
        if selected:
            # Execute skill
            result = orchestrator.execute_skill(
                skill_id=selected.id,
                input_data={"input": "test"},
                stage_id="test_stage",
                role_id="test_role"
            )
            
            assert result is not None
    
    def test_skill_benchmark(self, workflow_engine, sample_skill, sample_workflow_config):
        """Test skill benchmarking."""
        workflow_engine.load_all_configs(
            skill_file=sample_workflow_config["workflow_dir"] / "skills",
            roles_file=sample_workflow_config["workflow_dir"] / "role_schema.yaml",
            workflow_file=sample_workflow_config["workflow_dir"] / "workflow_schema.yaml"
        )
        
        orchestrator = AgentOrchestrator(workflow_engine)
        benchmark = SkillBenchmark(workflow_engine, orchestrator)
        
        test_cases = [
            {
                "name": "test_case_1",
                "input": {"input": "test"},
                "expected_output": {}
            }
        ]
        
        result = benchmark.benchmark_skill("test_skill", test_cases)
        
        assert result["skill_id"] == "test_skill"
        assert result["total_tests"] == 1
        assert "success_rate" in result
        assert "results" in result

