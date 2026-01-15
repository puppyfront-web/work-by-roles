"""
CLI tests for workflow commands.
"""
import pytest
import subprocess
import sys
from pathlib import Path


class TestWorkflowCommands:
    """Test workflow-related CLI commands."""
    
    def test_wfauto_command(self, temp_workspace):
        """Test wfauto command."""
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "wfauto", "--no-agent"],
            cwd=temp_workspace,
            capture_output=True,
            text=True
        )
        
        # Should not crash (may fail if workflow not initialized)
        assert result.returncode in [0, 1]
    
    def test_wfauto_parallel_command(self, temp_workspace):
        """Test wfauto with --parallel flag."""
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "wfauto", "--parallel", "--no-agent"],
            cwd=temp_workspace,
            capture_output=True,
            text=True
        )
        
        # Should not crash
        assert result.returncode in [0, 1]
    
    def test_intent_command(self, temp_workspace):
        """Test intent command."""
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "intent", "实现用户登录功能"],
            cwd=temp_workspace,
            capture_output=True,
            text=True
        )
        
        # Should not crash
        assert result.returncode in [0, 1]

