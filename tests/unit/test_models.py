"""
Unit tests for data models.
"""
import pytest
from datetime import datetime
from pathlib import Path

from work_by_roles.core.models import (
    AgentMessage, Task, TaskDecomposition, AgentContext, ExecutionState,
    ProjectContext, Role, Stage, Workflow, Skill
)
from work_by_roles.core.enums import StageStatus


class TestAgentMessage:
    """Test AgentMessage model."""
    
    def test_agent_message_creation(self):
        """Test creating an AgentMessage."""
        message = AgentMessage(
            from_agent="agent1",
            to_agent="agent2",
            message_type="request",
            content={"question": "test"}
        )
        
        assert message.from_agent == "agent1"
        assert message.to_agent == "agent2"
        assert message.message_type == "request"
        assert message.content == {"question": "test"}
        assert message.message_id != ""
        assert isinstance(message.timestamp, datetime)
    
    def test_agent_message_id_generation(self):
        """Test message ID is auto-generated."""
        message1 = AgentMessage(
            from_agent="agent1",
            to_agent="agent2",
            message_type="request",
            content={}
        )
        message2 = AgentMessage(
            from_agent="agent1",
            to_agent="agent2",
            message_type="request",
            content={}
        )
        
        assert message1.message_id != message2.message_id
    
    def test_agent_message_serialization(self):
        """Test message serialization."""
        message = AgentMessage(
            from_agent="agent1",
            to_agent="agent2",
            message_type="request",
            content={"test": "data"}
        )
        
        data = message.to_dict()
        assert data["from_agent"] == "agent1"
        assert data["to_agent"] == "agent2"
        assert data["message_type"] == "request"
        assert data["content"] == {"test": "data"}
        assert "timestamp" in data
        assert "message_id" in data
    
    def test_agent_message_deserialization(self):
        """Test message deserialization."""
        data = {
            "message_id": "test_id",
            "from_agent": "agent1",
            "to_agent": "agent2",
            "message_type": "request",
            "content": {"test": "data"},
            "timestamp": datetime.now().isoformat()
        }
        
        message = AgentMessage.from_dict(data)
        assert message.from_agent == "agent1"
        assert message.to_agent == "agent2"
        assert message.message_type == "request"
        assert message.content == {"test": "data"}
        assert message.message_id == "test_id"


class TestTask:
    """Test Task model."""
    
    def test_task_creation(self):
        """Test creating a Task."""
        task = Task(
            id="task1",
            description="Test task",
            category="general",
            assigned_role="role1"
        )
        
        assert task.id == "task1"
        assert task.description == "Test task"
        assert task.category == "general"
        assert task.assigned_role == "role1"
        assert task.status == "pending"
        assert task.dependencies == []
        assert task.priority == 0
    
    def test_task_with_dependencies(self):
        """Test task with dependencies."""
        task = Task(
            id="task2",
            description="Test task",
            category="general",
            assigned_role="role1",
            dependencies=["task1"]
        )
        
        assert task.dependencies == ["task1"]
    
    def test_task_status_transition(self):
        """Test task status transitions."""
        task = Task(
            id="task1",
            description="Test task",
            category="general",
            assigned_role="role1"
        )
        
        assert task.status == "pending"
        task.status = "in_progress"
        assert task.status == "in_progress"
        task.status = "completed"
        assert task.status == "completed"


class TestTaskDecomposition:
    """Test TaskDecomposition model."""
    
    def test_task_decomposition_creation(self):
        """Test creating a TaskDecomposition."""
        tasks = [
            Task(id="task1", description="Task 1", category="general", assigned_role="role1"),
            Task(id="task2", description="Task 2", category="general", assigned_role="role2", dependencies=["task1"])
        ]
        
        decomposition = TaskDecomposition(
            tasks=tasks,
            execution_order=["task1", "task2"],
            dependencies={"task2": ["task1"]}
        )
        
        assert len(decomposition.tasks) == 2
        assert decomposition.execution_order == ["task1", "task2"]
        assert decomposition.dependencies == {"task2": ["task1"]}
    
    def test_get_ready_tasks(self):
        """Test getting ready tasks."""
        tasks = [
            Task(id="task1", description="Task 1", category="general", assigned_role="role1", status="completed"),
            Task(id="task2", description="Task 2", category="general", assigned_role="role2", dependencies=["task1"], status="pending")
        ]
        
        decomposition = TaskDecomposition(
            tasks=tasks,
            execution_order=["task1", "task2"],
            dependencies={"task2": ["task1"]}
        )
        
        ready = decomposition.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "task2"
    
    def test_get_task(self):
        """Test getting task by ID."""
        tasks = [
            Task(id="task1", description="Task 1", category="general", assigned_role="role1"),
            Task(id="task2", description="Task 2", category="general", assigned_role="role2")
        ]
        
        decomposition = TaskDecomposition(
            tasks=tasks,
            execution_order=["task1", "task2"],
            dependencies={}
        )
        
        task = decomposition.get_task("task1")
        assert task is not None
        assert task.id == "task1"
        
        task = decomposition.get_task("nonexistent")
        assert task is None
    
    def test_validate_no_errors(self):
        """Test validation with valid decomposition."""
        tasks = [
            Task(id="task1", description="Task 1", category="general", assigned_role="role1"),
            Task(id="task2", description="Task 2", category="general", assigned_role="role2", dependencies=["task1"])
        ]
        
        decomposition = TaskDecomposition(
            tasks=tasks,
            execution_order=["task1", "task2"],
            dependencies={"task2": ["task1"]}
        )
        
        errors = decomposition.validate()
        assert len(errors) == 0
    
    def test_validate_missing_dependency(self):
        """Test validation detects missing dependency."""
        tasks = [
            Task(id="task1", description="Task 1", category="general", assigned_role="role1"),
            Task(id="task2", description="Task 2", category="general", assigned_role="role2", dependencies=["task3"])
        ]
        
        decomposition = TaskDecomposition(
            tasks=tasks,
            execution_order=["task1", "task2"],
            dependencies={"task2": ["task3"]}
        )
        
        errors = decomposition.validate()
        assert len(errors) > 0
        assert any("task3" in error for error in errors)
    
    def test_validate_circular_dependency(self):
        """Test validation detects circular dependencies."""
        tasks = [
            Task(id="task1", description="Task 1", category="general", assigned_role="role1", dependencies=["task2"]),
            Task(id="task2", description="Task 2", category="general", assigned_role="role2", dependencies=["task1"])
        ]
        
        decomposition = TaskDecomposition(
            tasks=tasks,
            execution_order=["task1", "task2"],
            dependencies={"task1": ["task2"], "task2": ["task1"]}
        )
        
        errors = decomposition.validate()
        assert len(errors) > 0
        assert any("circular" in error.lower() for error in errors)


class TestAgentContext:
    """Test AgentContext model."""
    
    def test_agent_context_creation(self, temp_workspace):
        """Test creating an AgentContext."""
        context = AgentContext(
            goal="Test goal",
            workspace_path=temp_workspace
        )
        
        assert context.goal == "Test goal"
        assert context.workspace_path == temp_workspace
        assert context.inputs == {}
        assert context.outputs == {}
        assert context.decisions == []
        assert context.shared_contexts == {}
    
    def test_agent_context_with_shared_contexts(self, temp_workspace):
        """Test AgentContext with shared contexts."""
        shared_context = AgentContext(
            goal="Shared goal",
            workspace_path=temp_workspace
        )
        
        context = AgentContext(
            goal="Main goal",
            workspace_path=temp_workspace,
            shared_contexts={"agent1": shared_context}
        )
        
        assert len(context.shared_contexts) == 1
        assert "agent1" in context.shared_contexts
        assert context.shared_contexts["agent1"].goal == "Shared goal"


class TestExecutionState:
    """Test ExecutionState model."""
    
    def test_execution_state_creation(self):
        """Test creating an ExecutionState."""
        state = ExecutionState()
        
        assert state.current_stage is None
        assert state.stage_status == {}
        assert state.completed_stages == set()
        assert state.current_role is None
        assert state.violations == []
        assert state.active_agents == []
    
    def test_execution_state_serialization(self):
        """Test ExecutionState serialization."""
        state = ExecutionState()
        state.current_stage = "stage1"
        state.stage_status = {"stage1": StageStatus.IN_PROGRESS}
        state.completed_stages = {"stage0"}
        state.current_role = "role1"
        state.active_agents = ["agent1", "agent2"]
        
        data = state.to_dict()
        assert data["current_stage"] == "stage1"
        assert data["stage_status"]["stage1"] == StageStatus.IN_PROGRESS.value
        assert "stage0" in data["completed_stages"]
        assert data["current_role"] == "role1"
        assert data["active_agents"] == ["agent1", "agent2"]
    
    def test_execution_state_deserialization(self):
        """Test ExecutionState deserialization."""
        data = {
            "current_stage": "stage1",
            "stage_status": {"stage1": StageStatus.IN_PROGRESS.value},
            "completed_stages": ["stage0"],
            "current_role": "role1",
            "violations": [],
            "active_agents": ["agent1", "agent2"]
        }
        
        state = ExecutionState.from_dict(data)
        assert state.current_stage == "stage1"
        assert state.stage_status["stage1"] == StageStatus.IN_PROGRESS
        assert "stage0" in state.completed_stages
        assert state.current_role == "role1"
        assert state.active_agents == ["agent1", "agent2"]

