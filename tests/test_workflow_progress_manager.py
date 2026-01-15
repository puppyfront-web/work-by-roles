"""
Tests for workflow progress manager.
"""

import pytest
from pathlib import Path
from datetime import datetime
import tempfile
import shutil
import json

from work_by_roles.core.workflow_progress_manager import (
    WorkflowProgressManager,
    ProgressStep,
    WorkflowProgress
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace"""
    temp_dir = tempfile.mkdtemp(prefix="test_progress_")
    workspace = Path(temp_dir)
    (workspace / ".workflow").mkdir(parents=True, exist_ok=True)
    yield workspace
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_progress_manager_start_workflow(temp_workspace):
    """Test starting a workflow"""
    manager = WorkflowProgressManager(temp_workspace)
    progress = manager.start_workflow("test_workflow")
    
    assert progress.workflow_id == "test_workflow"
    assert progress.overall_progress == 0.0
    assert progress.started_at is not None
    assert manager.current_progress == progress


def test_progress_manager_start_stage(temp_workspace):
    """Test starting a stage"""
    manager = WorkflowProgressManager(temp_workspace)
    manager.start_workflow("test_workflow")
    step = manager.start_stage("stage1", "Stage 1")
    
    assert step.step_id == "stage1"
    assert step.name == "Stage 1"
    assert step.status == "running"
    assert step.start_time is not None
    assert manager.current_progress.current_stage == "stage1"


def test_progress_manager_update_stage(temp_workspace):
    """Test updating stage status"""
    manager = WorkflowProgressManager(temp_workspace)
    manager.start_workflow("test_workflow")
    manager.start_stage("stage1", "Stage 1")
    
    manager.update_stage("stage1", status="completed", details={"action": "done"})
    
    step = manager._get_step("stage1")
    assert step.status == "completed"
    assert step.end_time is not None
    assert step.details["action"] == "done"


def test_progress_manager_progress_calculation(temp_workspace):
    """Test overall progress calculation"""
    manager = WorkflowProgressManager(temp_workspace)
    manager.start_workflow("test_workflow")
    
    manager.start_stage("stage1", "Stage 1")
    manager.update_stage("stage1", status="completed")
    
    assert manager.current_progress.overall_progress == 1.0
    
    manager.start_stage("stage2", "Stage 2")
    assert manager.current_progress.overall_progress == 0.5  # 1 completed out of 2


def test_progress_manager_save_load(temp_workspace):
    """Test saving and loading progress"""
    manager = WorkflowProgressManager(temp_workspace)
    manager.start_workflow("test_workflow")
    manager.start_stage("stage1", "Stage 1")
    manager.update_stage("stage1", status="completed", output_files=["file1.md"])
    
    # Create new manager and load
    manager2 = WorkflowProgressManager(temp_workspace)
    loaded = manager2.load_progress()
    
    assert loaded is not None
    assert loaded.workflow_id == "test_workflow"
    assert len(loaded.stages) == 1
    assert loaded.stages[0].step_id == "stage1"
    assert loaded.stages[0].status == "completed"
    assert "file1.md" in loaded.stages[0].output_files


def test_progress_manager_get_progress_markdown(temp_workspace):
    """Test generating progress markdown"""
    manager = WorkflowProgressManager(temp_workspace)
    manager.start_workflow("test_workflow")
    manager.start_stage("stage1", "Stage 1")
    manager.update_stage("stage1", status="completed")
    
    markdown = manager.get_progress_markdown()
    
    assert "工作流进度" in markdown
    assert "Stage 1" in markdown
    assert "100%" in markdown or "completed" in markdown.lower()


def test_progress_step_serialization():
    """Test ProgressStep serialization"""
    step = ProgressStep(
        step_id="test",
        name="Test",
        status="running",
        start_time=datetime.now(),
        details={"key": "value"},
        output_files=["file1.md"]
    )
    
    data = step.to_dict()
    assert data["step_id"] == "test"
    assert data["status"] == "running"
    assert "start_time" in data
    
    # Test deserialization
    step2 = ProgressStep.from_dict(data)
    assert step2.step_id == "test"
    assert step2.status == "running"

