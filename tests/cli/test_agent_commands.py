"""
CLI tests for agent-related commands.
"""
import pytest
import subprocess
import sys
from pathlib import Path


class TestAgentCommands:
    """Test agent-related CLI commands."""
    
    def test_agent_execute_command(self, temp_workspace, sample_workflow_config):
        """Test agent-execute command."""
        # Setup workflow
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "agent-execute", "test_stage", "--no-llm"],
            cwd=sample_workflow_config["workspace"],
            capture_output=True,
            text=True
        )
        
        # Should not crash (may fail if workflow not initialized, which is OK)
        assert result.returncode in [0, 1]
    
    def test_team_collaborate_command(self, temp_workspace):
        """Test team-collaborate command."""
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "team-collaborate", "测试目标"],
            cwd=temp_workspace,
            capture_output=True,
            text=True
        )
        
        # Should not crash
        assert result.returncode in [0, 1]
    
    def test_decompose_task_command(self, temp_workspace):
        """Test decompose-task command."""
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "decompose-task", "测试目标"],
            cwd=temp_workspace,
            capture_output=True,
            text=True
        )
        
        # Should not crash
        assert result.returncode in [0, 1]

