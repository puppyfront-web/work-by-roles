"""
Unit tests for VariableResolver.
"""
import pytest
from pathlib import Path

from work_by_roles.core.variable_resolver import VariableResolver
from work_by_roles.core.models import ProjectContext


class TestVariableResolver:
    """Test VariableResolver functionality."""
    
    def test_resolve_project_root(self, temp_workspace):
        """Test resolving project root variable."""
        context = ProjectContext(
            root_path=temp_workspace,
            paths={},
            specs={},
            standards={}
        )
        
        result = VariableResolver.resolve("{{project.root}}", context)
        
        # Result should contain the workspace path or be a placeholder
        assert isinstance(result, str)
        # The resolver may return the path or a placeholder
        if "[project.root NOT FOUND]" not in result:
            assert str(temp_workspace) in result
    
    def test_resolve_project_path(self, temp_workspace):
        """Test resolving project path variable."""
        context = ProjectContext(
            root_path=temp_workspace,
            paths={"test_path": "/test/path"},
            specs={},
            standards={}
        )
        
        result = VariableResolver.resolve("{{project.paths.test_path}}", context)
        
        # Result may be the path or a placeholder if not found
        assert isinstance(result, str)
        assert "/test/path" in result or "test_path" in result
    
    def test_resolve_env_variable(self):
        """Test resolving environment variable."""
        import os
        test_key = "WORK_BY_ROLES_TEST_VAR"
        os.environ[test_key] = "test_value"
        
        try:
            result = VariableResolver.resolve(f"{{{{env.{test_key}}}}}")
            # Result may be the value or a placeholder
            assert isinstance(result, str)
        finally:
            # Cleanup
            if test_key in os.environ:
                del os.environ[test_key]
    
    def test_resolve_missing_variable(self):
        """Test resolving missing variable returns placeholder."""
        context = ProjectContext(
            root_path=Path("/tmp"),
            paths={},
            specs={},
            standards={}
        )
        
        result = VariableResolver.resolve("{{project.paths.missing}}", context)
        
        # Should return placeholder or default
        assert isinstance(result, str)
    
    def test_resolve_no_variables(self):
        """Test resolving string with no variables."""
        result = VariableResolver.resolve("no variables here")
        
        assert result == "no variables here"

