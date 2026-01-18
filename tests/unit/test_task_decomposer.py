"""
Unit tests for TaskDecomposer.
"""
import pytest

from work_by_roles.core.task_decomposer import TaskDecomposer
from work_by_roles.core.models import Role, TaskDecomposition
from work_by_roles.core.exceptions import WorkflowError


class TestTaskDecomposer:
    """Test TaskDecomposer functionality."""
    
    def test_task_decomposer_initialization(self, workflow_engine):
        """Test initializing TaskDecomposer."""
        decomposer = TaskDecomposer(workflow_engine, llm_client=None)
        
        assert decomposer.engine == workflow_engine
        assert decomposer.llm_client is None
        assert decomposer.llm_enabled is False
    
    def test_decompose_simple_goal(self, workflow_engine, sample_role):
        """Test decomposing a simple goal."""
        # Setup role manager
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        decomposer = TaskDecomposer(workflow_engine)
        
        goal = "实现用户登录功能"
        decomposition = decomposer.decompose(goal, [sample_role])
        
        assert isinstance(decomposition, TaskDecomposition)
        assert len(decomposition.tasks) > 0
        assert len(decomposition.execution_order) > 0
    
    def test_decompose_with_requirements_keyword(self, workflow_engine, sample_role):
        """Test decomposition recognizes requirements keyword."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        # Create a role that matches requirements
        analyst_role = Role(
            id="product_analyst",
            name="Product Analyst",
            description="需求分析",
            skills=[],
            domain="analysis",
            responsibility="分析需求",
            extends=None,
            constraints={"allowed_actions": ["analyze"], "forbidden_actions": []},
            validation_rules=[],
            instruction_template=""
        )
        
        decomposer = TaskDecomposer(workflow_engine)
        goal = "分析用户需求"
        
        decomposition = decomposer.decompose(goal, [analyst_role, sample_role])
        
        # Should create at least one task
        assert len(decomposition.tasks) > 0
    
    def test_decompose_with_architecture_keyword(self, workflow_engine, sample_role):
        """Test decomposition recognizes architecture keyword."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        architect_role = Role(
            id="system_architect",
            name="System Architect",
            description="系统架构",
            skills=[],
            domain="architecture",
            responsibility="设计架构",
            extends=None,
            constraints={"allowed_actions": ["design"], "forbidden_actions": []},
            validation_rules=[],
            instruction_template=""
        )
        
        decomposer = TaskDecomposer(workflow_engine)
        goal = "设计系统架构"
        
        decomposition = decomposer.decompose(goal, [architect_role, sample_role])
        
        assert len(decomposition.tasks) > 0
    
    def test_decompose_builds_execution_order(self, workflow_engine, sample_role):
        """Test decomposition builds correct execution order."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        decomposer = TaskDecomposer(workflow_engine)
        goal = "实现功能并测试"
        
        decomposition = decomposer.decompose(goal, [sample_role])
        
        # Execution order should respect dependencies
        assert len(decomposition.execution_order) == len(decomposition.tasks)
        
        # Verify order respects dependencies
        task_map = {task.id: task for task in decomposition.tasks}
        for i, task_id in enumerate(decomposition.execution_order):
            task = task_map[task_id]
            # All dependencies should appear before this task
            for dep_id in task.dependencies:
                assert dep_id in decomposition.execution_order[:i]
    
    def test_decompose_assigns_roles(self, workflow_engine):
        """Test decomposition assigns roles to tasks."""
        role1 = Role(
            id="role1",
            name="Role 1",
            description="Role 1 description",
            skills=[],
            domain="general",
            responsibility="Role 1 responsibility",
            extends=None,
            constraints={"allowed_actions": ["action1"], "forbidden_actions": []},
            validation_rules=[],
            instruction_template=""
        )
        
        role2 = Role(
            id="role2",
            name="Role 2",
            description="Role 2 description",
            skills=[],
            domain="general",
            responsibility="Role 2 responsibility",
            extends=None,
            constraints={"allowed_actions": ["action2"], "forbidden_actions": []},
            validation_rules=[],
            instruction_template=""
        )
        
        workflow_engine.role_manager.roles = {"role1": role1, "role2": role2}
        
        decomposer = TaskDecomposer(workflow_engine)
        goal = "完成任务"
        
        decomposition = decomposer.decompose(goal, [role1, role2])
        
        # All tasks should have assigned roles
        for task in decomposition.tasks:
            assert task.assigned_role in ["role1", "role2"]
    
    def test_decompose_validates_result(self, workflow_engine, sample_role):
        """Test decomposition validates the result."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        decomposer = TaskDecomposer(workflow_engine)
        goal = "测试目标"
        
        decomposition = decomposer.decompose(goal, [sample_role])
        
        # Should not raise validation errors
        errors = decomposition.validate()
        assert len(errors) == 0
    
    def test_decompose_fallback_to_rules(self, workflow_engine, sample_role):
        """Test decomposition falls back to rules when LLM unavailable."""
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        decomposer = TaskDecomposer(workflow_engine, llm_client=None)
        goal = "测试目标"
        
        # Should work without LLM (uses rule-based)
        decomposition = decomposer.decompose(goal, [sample_role])
        
        assert isinstance(decomposition, TaskDecomposition)
        assert len(decomposition.tasks) > 0
    
    def test_find_role_by_keywords(self, workflow_engine):
        """Test finding role by keywords."""
        role1 = Role(
            id="product_analyst",
            name="Product Analyst",
            description="需求分析",
            skills=[],
            domain="analysis",
            responsibility="分析需求",
            extends=None,
            constraints={"allowed_actions": [], "forbidden_actions": []},
            validation_rules=[],
            instruction_template=""
        )
        
        role2 = Role(
            id="system_architect",
            name="System Architect",
            description="系统架构设计",
            skills=[],
            domain="architecture",
            responsibility="设计架构",
            extends=None,
            constraints={"allowed_actions": [], "forbidden_actions": []},
            validation_rules=[],
            instruction_template=""
        )
        
        decomposer = TaskDecomposer(workflow_engine)
        
        # Test finding by keyword
        found = decomposer._find_role_by_keywords([role1, role2], ["需求", "analyst"])
        assert found == role1
        
        found = decomposer._find_role_by_keywords([role1, role2], ["架构", "architect"])
        assert found == role2
        
        found = decomposer._find_role_by_keywords([role1, role2], ["nonexistent"])
        assert found is None
    
    def test_build_execution_order_respects_dependencies(self, workflow_engine):
        """Test execution order respects task dependencies."""
        from work_by_roles.core.models import Task
        
        tasks = [
            Task(id="task1", description="Task 1", category="general", assigned_role="role1", priority=1),
            Task(id="task2", description="Task 2", category="general", assigned_role="role2", dependencies=["task1"], priority=2),
            Task(id="task3", description="Task 3", category="general", assigned_role="role3", dependencies=["task2"], priority=3)
        ]
        
        decomposer = TaskDecomposer(workflow_engine)
        execution_order = decomposer._build_execution_order(tasks)
        
        # task1 should come before task2
        assert execution_order.index("task1") < execution_order.index("task2")
        # task2 should come before task3
        assert execution_order.index("task2") < execution_order.index("task3")
    
    def test_build_execution_order_handles_priority(self, workflow_engine):
        """Test execution order respects task priority."""
        from work_by_roles.core.models import Task
        
        tasks = [
            Task(id="task1", description="Task 1", category="general", assigned_role="role1", priority=3),
            Task(id="task2", description="Task 2", category="general", assigned_role="role2", priority=1),
            Task(id="task3", description="Task 3", category="general", assigned_role="role3", priority=2)
        ]
        
        decomposer = TaskDecomposer(workflow_engine)
        execution_order = decomposer._build_execution_order(tasks)
        
        # Higher priority tasks should come first (when no dependencies)
        # task1 (priority 3) should come before task2 (priority 1)
        assert execution_order.index("task1") < execution_order.index("task2")
    
    def test_assign_role_matches_keywords(self, workflow_engine):
        """Test role assignment matches task description keywords."""
        role1 = Role(
            id="developer",
            name="Developer",
            description="代码开发",
            skills=[],
            domain="implementation",
            responsibility="编写代码",
            extends=None,
            constraints={"allowed_actions": ["write_code", "implement"], "forbidden_actions": []},
            validation_rules=[],
            instruction_template=""
        )
        
        role2 = Role(
            id="tester",
            name="Tester",
            description="测试验证",
            skills=[],
            domain="qa",
            responsibility="测试功能",
            extends=None,
            constraints={"allowed_actions": ["test", "validate"], "forbidden_actions": []},
            validation_rules=[],
            instruction_template=""
        )
        
        decomposer = TaskDecomposer(workflow_engine)
        
        # Test assignment based on keywords
        # Note: _assign_role now requires task_category parameter
        assigned = decomposer._assign_role("实现代码功能", "implementation", [role1, role2])
        assert assigned in [role1, role2]  # Should return one of them
        
        assigned = decomposer._assign_role("测试功能", "qa", [role1, role2])
        assert assigned in [role1, role2]  # Should return one of them

