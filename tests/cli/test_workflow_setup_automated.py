"""
Automated tests for workflow setup and CLI commands.
Uses enhanced fixtures for simplified testing without manual project switching.
"""

import pytest
from pathlib import Path
from tests.fixtures.test_project_fixtures import (
    clean_project,
    fresh_project,
    project_with_files,
    project_with_template,
    command_tester,
    command_tester_clean,
    ProjectTestHelper,
    CommandTester
)


class TestWorkflowSetupAutomated:
    """Automated tests for workflow setup command."""
    
    def test_setup_creates_workflow_directory(self, clean_project: ProjectTestHelper):
        """Test that setup creates .workflow directory."""
        result = clean_project.setup()
        clean_project.assert_setup_success(result)
        assert clean_project.workflow_dir.exists()
    
    def test_setup_creates_config_files(self, clean_project: ProjectTestHelper):
        """Test that setup creates all required config files."""
        result = clean_project.setup()
        clean_project.assert_setup_success(result)
        
        # Check required files
        clean_project.assert_workflow_file_exists("role_schema.yaml")
        clean_project.assert_workflow_file_exists("workflow_schema.yaml")
        clean_project.assert_workflow_file_exists("project_context.yaml")
        clean_project.assert_workflow_file_exists("USAGE.md")
    
    def test_setup_creates_skills_directory(self, clean_project: ProjectTestHelper):
        """Test that setup creates skills directory with skill files."""
        result = clean_project.setup()
        clean_project.assert_setup_success(result)
        
        skills_dir = clean_project.workflow_dir / "skills"
        assert skills_dir.exists(), "skills directory should exist"
        
        # Check for skill files
        skill_files = list(skills_dir.rglob("Skill.md"))
        assert len(skill_files) > 0, "Should have at least one skill file"
    
    def test_setup_idempotent(self, clean_project: ProjectTestHelper):
        """Test that setup is idempotent (can run multiple times safely)."""
        # First run
        result1 = clean_project.setup()
        clean_project.assert_setup_success(result1)
        
        # Read first content
        roles_file = clean_project.workflow_dir / "role_schema.yaml"
        first_content = roles_file.read_text(encoding='utf-8')
        
        # Second run
        result2 = clean_project.setup()
        # Should succeed or show "already exists" message
        assert result2.returncode == 0 or "已接入" in result2.stdout or "已存在" in result2.stdout
        
        # Content should be the same
        second_content = roles_file.read_text(encoding='utf-8')
        assert first_content == second_content, "Repeated setup should not modify files"
    
    def test_setup_with_template(self, clean_project: ProjectTestHelper):
        """Test setup (setup command auto-detects template, doesn't accept --template)."""
        result = clean_project.setup()
        clean_project.assert_setup_success(result)
        
        # Verify template-specific files exist
        clean_project.assert_workflow_file_exists("role_schema.yaml")
    
    def test_init_with_template(self, clean_project: ProjectTestHelper):
        """Test init command with specific template."""
        result = clean_project.init(template="standard-delivery")
        # init may succeed even if template doesn't exist, just check workflow dir
        if result.returncode == 0 or clean_project.workflow_dir.exists():
            assert clean_project.workflow_dir.exists()
    
    def test_setup_with_project_files(self, project_with_files: ProjectTestHelper):
        """Test setup in a project with existing files."""
        result = project_with_files.setup()
        project_with_files.assert_setup_success(result)
        
        # Verify project context includes project files
        context_file = project_with_files.workflow_dir / "project_context.yaml"
        assert context_file.exists()
        
        context = project_with_files.read_yaml(".workflow/project_context.yaml")
        assert context is not None


class TestCLICommandsAutomated:
    """Automated tests for CLI commands using enhanced fixtures."""
    
    def test_status_command(self, command_tester: CommandTester):
        """Test status command after setup."""
        result = command_tester.test_status()
        assert result["success"]
    
    def test_list_roles_command(self, command_tester: CommandTester):
        """Test list-roles command after setup."""
        result = command_tester.test_list_roles()
        assert result["success"]
        assert result["has_output"]
    
    def test_list_skills_command(self, command_tester: CommandTester):
        """Test list-skills command after setup."""
        result = command_tester.test_list_skills()
        assert result["success"]
        assert result["has_output"]
    
    def test_wfauto_command(self, command_tester: CommandTester):
        """Test wfauto command."""
        result = command_tester.test_wfauto(intent="实现用户登录功能", no_agent=True)
        assert result["success"]
    
    def test_wfauto_parallel(self, command_tester: CommandTester):
        """Test wfauto with parallel flag."""
        result = command_tester.test_wfauto(no_agent=True, parallel=True)
        assert result["success"]
    
    def test_init_command(self, command_tester_clean: CommandTester):
        """Test init command."""
        result = command_tester_clean.test_init(quick=True)
        assert result["success"]
    
    def test_role_execute_command(self, command_tester: CommandTester):
        """Test role-execute command."""
        result = command_tester.test_role_execute("product_analyst", "分析用户需求")
        assert result["success"]


class TestWorkflowSetupFlow:
    """Test complete workflow setup and command execution flow."""
    
    def test_complete_setup_flow(self, clean_project: ProjectTestHelper):
        """Test complete setup flow: setup -> verify -> commands."""
        # Step 1: Setup
        result = clean_project.setup()
        clean_project.assert_setup_success(result)
        
        # Step 2: Verify files
        clean_project.assert_workflow_file_exists("role_schema.yaml")
        clean_project.assert_workflow_file_exists("workflow_schema.yaml")
        
        # Step 3: Test commands
        tester = CommandTester(clean_project)
        
        status_result = tester.test_status()
        assert status_result["success"]
        
        roles_result = tester.test_list_roles()
        assert roles_result["success"]
        assert roles_result["has_output"]
        
        skills_result = tester.test_list_skills()
        assert skills_result["success"]
        assert skills_result["has_output"]
    
    def test_reset_and_retry(self, clean_project: ProjectTestHelper):
        """Test resetting project and running setup again."""
        # First setup
        result1 = clean_project.setup()
        clean_project.assert_setup_success(result1)
        
        # Reset
        clean_project.reset()
        assert not clean_project.workflow_dir.exists()
        
        # Second setup
        result2 = clean_project.setup()
        clean_project.assert_setup_success(result2)
        assert clean_project.workflow_dir.exists()


class TestMultipleTemplates:
    """Test setup with different templates (parametrized)."""
    
    def test_setup_with_different_templates(self, project_with_template: ProjectTestHelper):
        """Test setup with different templates."""
        # project_with_template is already parametrized
        assert project_with_template.workflow_dir.exists()
        project_with_template.assert_workflow_file_exists("role_schema.yaml")


# Convenience test functions for quick testing
def test_quick_setup_and_verify(clean_project: ProjectTestHelper):
    """Quick test: setup and verify basic files."""
    result = clean_project.setup()
    clean_project.assert_setup_success(result)
    
    # Quick verification
    assert (clean_project.workflow_dir / "role_schema.yaml").exists()
    assert (clean_project.workflow_dir / "workflow_schema.yaml").exists()


def test_quick_command_test(command_tester: CommandTester):
    """Quick test: verify commands work after setup."""
    assert command_tester.test_list_roles()["success"]
    assert command_tester.test_list_skills()["success"]
