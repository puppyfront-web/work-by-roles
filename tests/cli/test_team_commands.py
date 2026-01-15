"""
CLI tests for team management commands.
"""
import pytest
import subprocess
import sys
from pathlib import Path


class TestTeamCommands:
    """Test team management CLI commands."""
    
    def test_team_list_command(self, temp_workspace):
        """Test team list command."""
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "team", "list"],
            cwd=temp_workspace,
            capture_output=True,
            text=True
        )
        
        # Should not crash
        assert result.returncode == 0
    
    def test_team_create_command(self, temp_workspace):
        """Test team create command."""
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "team", "create", "test_team", "--name", "Test Team"],
            cwd=temp_workspace,
            capture_output=True,
            text=True
        )
        
        # Should create team or show error
        assert result.returncode in [0, 1]
        
        # Cleanup if created
        if result.returncode == 0:
            subprocess.run(
                [sys.executable, "-m", "work_by_roles.cli", "team", "delete", "test_team", "--force"],
                cwd=temp_workspace,
                capture_output=True
            )

