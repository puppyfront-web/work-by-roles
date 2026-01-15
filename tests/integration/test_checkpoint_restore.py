"""
Integration tests for checkpoint restore functionality.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from work_by_roles.core.workflow_engine import WorkflowEngine
from work_by_roles.core.checkpoint_manager import CheckpointManager
from work_by_roles.core.enums import StageStatus


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with workflow config"""
    temp_dir = tempfile.mkdtemp(prefix="test_checkpoint_restore_")
    workspace = Path(temp_dir)
    
    # Create minimal workflow config
    workflow_dir = workspace / ".workflow"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    
    # Create minimal workflow schema
    workflow_file = workflow_dir / "workflow_schema.yaml"
    workflow_file.write_text("""
schema_version: "1.0"
workflow:
  id: "test_workflow"
  name: "Test Workflow"
  description: "Test"
  stages:
    - id: "stage1"
      name: "Stage 1"
      role: "role1"
      order: 1
      prerequisites: []
      quality_gates: []
      outputs: []
""", encoding='utf-8')
    
    # Create minimal role schema
    role_file = workflow_dir / "role_schema.yaml"
    role_file.write_text("""
schema_version: "1.0"
roles:
  - id: "role1"
    name: "Role 1"
    description: "Test role"
    constraints:
      allowed_actions: []
      forbidden_actions: []
    required_skills: []
    validation_rules: []
""", encoding='utf-8')
    
    # Create minimal skill library
    skill_dir = workflow_dir / "skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    yield workspace
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_checkpoint_restore_integration(temp_workspace):
    """Test checkpoint creation and restore integration"""
    engine = WorkflowEngine(workspace_path=temp_workspace)
    
    # Load workflow
    engine.load_all_configs(
        skill_file=temp_workspace / ".workflow" / "skills",
        roles_file=temp_workspace / ".workflow" / "role_schema.yaml",
        workflow_file=temp_workspace / ".workflow" / "workflow_schema.yaml"
    )
    
    # Start a stage
    engine.start_stage("stage1", "role1")
    
    # Create checkpoint
    checkpoint = engine.create_checkpoint(
        name="Test Checkpoint",
        description="Integration test checkpoint",
        stage_id="stage1"
    )
    
    assert checkpoint is not None
    assert checkpoint.workflow_id == "test_workflow"
    assert checkpoint.stage_id == "stage1"
    
    # Create new engine and restore
    engine2 = WorkflowEngine(workspace_path=temp_workspace)
    engine2.load_all_configs(
        skill_file=temp_workspace / ".workflow" / "skills",
        roles_file=temp_workspace / ".workflow" / "role_schema.yaml",
        workflow_file=temp_workspace / ".workflow" / "workflow_schema.yaml"
    )
    
    result = engine2.restore_from_checkpoint(checkpoint.checkpoint_id)
    
    assert result["execution_state_restored"] is True
    assert engine2.executor.state.current_stage == "stage1"
    assert engine2.executor.state.current_role == "role1"

