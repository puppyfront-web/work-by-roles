"""
Unit tests for StateStorage.
"""
import pytest
import yaml
from pathlib import Path

from work_by_roles.core.state_storage import FileStateStorage
from work_by_roles.core.models import ExecutionState
from work_by_roles.core.enums import StageStatus


class TestStateStorage:
    """Test StateStorage functionality."""
    
    def test_file_storage_save_and_load(self, temp_workspace):
        """Test saving and loading state."""
        storage = FileStateStorage()
        state_file = temp_workspace / ".workflow" / "state.yaml"
        
        state = ExecutionState()
        state.current_stage = "test_stage"
        state.current_role = "test_role"
        state.stage_status = {"test_stage": StageStatus.IN_PROGRESS}
        state.completed_stages = {"stage0"}
        state.active_agents = ["agent1"]
        
        # Save
        storage.save(state, state_file)
        
        assert state_file.exists()
        
        # Load
        loaded_state = storage.load(state_file)
        
        assert loaded_state is not None
        assert loaded_state.current_stage == "test_stage"
        assert loaded_state.current_role == "test_role"
        assert "test_stage" in loaded_state.stage_status
        assert "stage0" in loaded_state.completed_stages
        assert "agent1" in loaded_state.active_agents
    
    def test_file_storage_load_nonexistent(self, temp_workspace):
        """Test loading non-existent state file."""
        storage = FileStateStorage()
        state_file = temp_workspace / ".workflow" / "nonexistent.yaml"
        
        loaded = storage.load(state_file)
        
        assert loaded is None

