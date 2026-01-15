"""
Tests for checkpoint manager.
"""

import pytest
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

from work_by_roles.core.checkpoint_manager import CheckpointManager
from work_by_roles.core.models import ExecutionState, Checkpoint
from work_by_roles.core.enums import StageStatus
from work_by_roles.core.workflow_progress_manager import WorkflowProgressManager


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace"""
    temp_dir = tempfile.mkdtemp(prefix="test_checkpoint_")
    workspace = Path(temp_dir)
    (workspace / ".workflow" / "checkpoints").mkdir(parents=True, exist_ok=True)
    yield workspace
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_create_checkpoint(temp_workspace):
    """Test creating a checkpoint"""
    manager = CheckpointManager(temp_workspace)
    
    execution_state = ExecutionState(
        current_stage="stage1",
        current_role="role1"
    )
    
    checkpoint = manager.create_checkpoint(
        workflow_id="test_workflow",
        execution_state=execution_state,
        name="Test Checkpoint",
        description="Test description",
        stage_id="stage1"
    )
    
    assert checkpoint.checkpoint_id.startswith("checkpoint_")
    assert checkpoint.name == "Test Checkpoint"
    assert checkpoint.workflow_id == "test_workflow"
    assert checkpoint.stage_id == "stage1"
    assert checkpoint.execution_state.current_stage == "stage1"


def test_list_checkpoints(temp_workspace):
    """Test listing checkpoints"""
    manager = CheckpointManager(temp_workspace)
    
    execution_state = ExecutionState(current_stage="stage1")
    
    # Create multiple checkpoints
    cp1 = manager.create_checkpoint("workflow1", execution_state, name="CP1")
    cp2 = manager.create_checkpoint("workflow1", execution_state, name="CP2")
    cp3 = manager.create_checkpoint("workflow2", execution_state, name="CP3")
    
    # List all
    all_checkpoints = manager.list_checkpoints()
    assert len(all_checkpoints) == 3
    
    # List by workflow
    workflow1_checkpoints = manager.list_checkpoints("workflow1")
    assert len(workflow1_checkpoints) == 2
    assert all(cp.workflow_id == "workflow1" for cp in workflow1_checkpoints)


def test_get_checkpoint(temp_workspace):
    """Test getting a checkpoint by ID"""
    manager = CheckpointManager(temp_workspace)
    
    execution_state = ExecutionState(current_stage="stage1")
    checkpoint = manager.create_checkpoint("workflow1", execution_state, name="Test")
    
    retrieved = manager.get_checkpoint(checkpoint.checkpoint_id)
    assert retrieved is not None
    assert retrieved.checkpoint_id == checkpoint.checkpoint_id
    assert retrieved.name == "Test"


def test_get_latest_checkpoint(temp_workspace):
    """Test getting the latest checkpoint"""
    manager = CheckpointManager(temp_workspace)
    
    execution_state = ExecutionState(current_stage="stage1")
    
    cp1 = manager.create_checkpoint("workflow1", execution_state, name="CP1")
    import time
    time.sleep(0.1)  # Ensure different timestamps
    cp2 = manager.create_checkpoint("workflow1", execution_state, name="CP2")
    
    latest = manager.get_latest_checkpoint("workflow1")
    assert latest is not None
    assert latest.checkpoint_id == cp2.checkpoint_id


def test_delete_checkpoint(temp_workspace):
    """Test deleting a checkpoint"""
    manager = CheckpointManager(temp_workspace)
    
    execution_state = ExecutionState(current_stage="stage1")
    checkpoint = manager.create_checkpoint("workflow1", execution_state, name="Test")
    
    deleted = manager.delete_checkpoint(checkpoint.checkpoint_id)
    assert deleted is True
    
    # Verify deleted
    retrieved = manager.get_checkpoint(checkpoint.checkpoint_id)
    assert retrieved is None


def test_restore_from_checkpoint(temp_workspace):
    """Test restoring from checkpoint"""
    manager = CheckpointManager(temp_workspace)
    
    execution_state = ExecutionState(
        current_stage="stage1",
        current_role="role1",
        completed_stages={"stage0"}
    )
    
    checkpoint = manager.create_checkpoint("workflow1", execution_state, name="Test")
    
    # Create a mock engine
    class MockEngine:
        def __init__(self):
            from work_by_roles.core.workflow_executor import WorkflowExecutor
            from work_by_roles.core.models import Workflow, Stage
            from work_by_roles.core.role_manager import RoleManager
            
            self.workspace_path = temp_workspace
            self.workflow = Workflow(id="workflow1", name="Test", description="", stages=[])
            self.executor = type('obj', (object,), {
                'state': ExecutionState()
            })()
    
    engine = MockEngine()
    result = manager.restore_from_checkpoint(checkpoint.checkpoint_id, engine)
    
    assert result["checkpoint_id"] == checkpoint.checkpoint_id
    assert result["execution_state_restored"] is True
    assert engine.executor.state.current_stage == "stage1"
    assert engine.executor.state.current_role == "role1"

