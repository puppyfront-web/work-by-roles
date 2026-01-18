"""
Unit tests for RoleManager.
"""
import pytest
import yaml
from pathlib import Path

from work_by_roles.core.role_manager import RoleManager
from work_by_roles.core.models import Role, Skill


class TestRoleManager:
    """Test RoleManager functionality."""
    
    def test_role_manager_initialization(self):
        """Test initializing RoleManager."""
        manager = RoleManager()
        
        assert manager.roles == {}
        # skill_library may be None initially
        assert manager.skill_library is None or manager.skill_library == {}
    
    def test_load_roles(self, temp_workspace):
        """Test loading roles from YAML."""
        manager = RoleManager()
        
        # First load skill library (required for roles with skills)
        skill_data = {
            "schema_version": "1.0",
            "skills": [
                {
                    "id": "test_skill",
                    "name": "Test Skill",
                    "description": "A test skill",
                    "category": "general",
                    "dimensions": ["test"],
                    "levels": {1: "Level 1"},
                    "tools": [],
                    "constraints": []
                }
            ]
        }
        manager.load_skill_library(skill_data)
        
        role_data = {
            "schema_version": "1.0",
            "roles": [
                {
                    "id": "test_role",
                    "name": "Test Role",
                    "description": "A test role",
                    "instruction_template": "Test instruction",
                    "extends": None,
                    "skills": ["test_skill"],
                    "domain": "general",
                    "responsibility": "Test responsibility",
                    "constraints": {
                        "allowed_actions": ["test_action"],
                        "forbidden_actions": []
                    },
                    "validation_rules": []
                }
            ]
        }
        
        manager.load_roles(role_data)
        
        assert "test_role" in manager.roles
        assert manager.roles["test_role"].id == "test_role"
    
    def test_load_skill_library(self, temp_workspace):
        """Test loading skill library."""
        manager = RoleManager()
        
        skill_data = {
            "schema_version": "1.0",
            "skills": [
                {
                    "id": "test_skill",
                    "name": "Test Skill",
                    "description": "A test skill",
                    "category": "general",
                    "dimensions": ["test"],
                    "levels": {1: "Level 1"},
                    "tools": [],
                    "constraints": [],
                    "metadata": {}
                }
            ]
        }
        
        manager.load_skill_library(skill_data)
        
        assert manager.skill_library is not None
        assert "test_skill" in manager.skill_library
        assert manager.skill_library["test_skill"].id == "test_skill"
    
    def test_get_role(self, sample_role):
        """Test getting a role."""
        manager = RoleManager()
        manager.roles = {"test_role": sample_role}
        
        role = manager.get_role("test_role")
        assert role == sample_role
        
        role = manager.get_role("nonexistent")
        assert role is None

