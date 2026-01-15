"""
Unit tests for TeamManager.
"""
import pytest
from pathlib import Path

from work_by_roles.core.team_manager import TeamManager


class TestTeamManager:
    """Test TeamManager functionality."""
    
    def test_team_manager_initialization(self, temp_workspace):
        """Test initializing TeamManager."""
        manager = TeamManager(temp_workspace)
        
        assert manager.workspace_path == temp_workspace
        assert manager.teams_file == temp_workspace / ".workflow" / "teams.yaml"
    
    def test_create_team(self, temp_workspace):
        """Test creating a team."""
        manager = TeamManager(temp_workspace)
        
        team_dir = manager.create_team(
            team_id="test_team",
            name="Test Team",
            description="A test team"
        )
        
        assert team_dir.exists()
        assert "test_team" in manager.teams
        
        # Cleanup
        manager.delete_team("test_team", remove_files=True)
    
    def test_list_teams(self, temp_workspace):
        """Test listing teams."""
        manager = TeamManager(temp_workspace)
        
        # Create a team
        manager.create_team("test_team", "Test Team")
        
        teams = manager.list_teams()
        
        assert len(teams) > 0
        assert any(t["id"] == "test_team" for t in teams)
        
        # Cleanup
        manager.delete_team("test_team", remove_files=True)
    
    def test_set_current_team(self, temp_workspace):
        """Test setting current team."""
        manager = TeamManager(temp_workspace)
        
        manager.create_team("test_team", "Test Team")
        manager.set_current_team("test_team")
        
        current = manager.get_current_team()
        assert current == "test_team"
        
        # Cleanup
        manager.delete_team("test_team", remove_files=True)
    
    def test_get_team_config(self, temp_workspace):
        """Test getting team configuration."""
        manager = TeamManager(temp_workspace)
        
        manager.create_team("test_team", "Test Team")
        config = manager.get_team_config("test_team")
        
        assert "workflow" in config
        assert "roles" in config
        assert "skills" in config
        assert "state" in config
        
        # Cleanup
        manager.delete_team("test_team", remove_files=True)
    
    def test_get_current_team_none(self, temp_workspace):
        """Test getting current team when none is set."""
        manager = TeamManager(temp_workspace)
        
        current = manager.get_current_team()
        assert current is None

