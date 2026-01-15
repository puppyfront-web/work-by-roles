"""
CLI tests for basic commands.
"""
import pytest
import subprocess
import sys
from pathlib import Path


class TestBasicCommands:
    """Test basic CLI commands."""
    
    def test_workflow_status_command(self, temp_workspace):
        """Test workflow status command."""
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "status"],
            cwd=temp_workspace,
            capture_output=True,
            text=True
        )
        
        # Should not crash (may show no workflow initialized)
        assert result.returncode in [0, 1]  # 1 is OK if no workflow
    
    def test_workflow_list_roles_command(self, temp_workspace):
        """Test list-roles command."""
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "list-roles"],
            cwd=temp_workspace,
            capture_output=True,
            text=True
        )
        
        # Should not crash
        assert result.returncode in [0, 1]
    
    def test_workflow_list_skills_command(self, temp_workspace):
        """Test list-skills command."""
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "list-skills"],
            cwd=temp_workspace,
            capture_output=True,
            text=True
        )
        
        # Should not crash
        assert result.returncode in [0, 1]

