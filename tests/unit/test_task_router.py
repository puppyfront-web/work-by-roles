"""
Unit tests for TaskRouter.
"""
import pytest

from work_by_roles.core.task_router import TaskRouter
from work_by_roles.core.models import Task, TaskAssignment, Role, Skill
from work_by_roles.core.role_manager import RoleManager


class TestTaskRouter:
    """Test TaskRouter functionality."""
    
    def test_task_router_initialization(self, temp_workspace):
        """Test initializing TaskRouter."""
        role_manager = RoleManager()
        router = TaskRouter(role_manager)
        
        assert router.role_manager == role_manager
        assert router.task_history == []
    
    def test_assign_task_auto_select(self, temp_workspace):
        """Test automatic role selection."""
        role_manager = RoleManager()
        
        # Load skill library
        skill_data = {
            "schema_version": "1.0",
            "skills": [
                {
                    "id": "frontend_skill",
                    "name": "Frontend Development",
                    "description": "Develop frontend components",
                    "category": "frontend"
                }
            ]
        }
        role_manager.load_skill_library(skill_data)
        
        # Load roles
        role_data = {
            "schema_version": "1.0",
            "roles": [
                {
                    "id": "frontend_engineer",
                    "name": "Frontend Engineer",
                    "description": "Frontend developer",
                    "skills": ["frontend_skill"],
                    "domain": "frontend",
                    "responsibility": "开发用户界面和前端组件",
                    "constraints": {},
                    "validation_rules": []
                }
            ]
        }
        role_manager.load_roles(role_data)
        
        router = TaskRouter(role_manager)
        
        # Create task without assigned role
        task = Task(
            id="task1",
            description="开发一个用户登录页面",
            category="frontend"
        )
        
        assignment = router.assign_task(task)
        
        assert assignment.status == "accepted"
        assert assignment.assigned_role == "frontend_engineer"
        assert task.assigned_role == "frontend_engineer"
        assert task.status == "accepted"
    
    def test_assign_task_with_feedback_rejection(self, temp_workspace):
        """Test task assignment with role rejection."""
        role_manager = RoleManager()
        
        # Load skill library
        skill_data = {
            "schema_version": "1.0",
            "skills": [
                {
                    "id": "backend_skill",
                    "name": "Backend Development",
                    "description": "Develop backend APIs",
                    "category": "backend"
                }
            ]
        }
        role_manager.load_skill_library(skill_data)
        
        # Load roles
        role_data = {
            "schema_version": "1.0",
            "roles": [
                {
                    "id": "backend_engineer",
                    "name": "Backend Engineer",
                    "description": "Backend developer",
                    "skills": ["backend_skill"],
                    "domain": "backend",
                    "responsibility": "开发API和服务",
                    "constraints": {
                        "forbidden_actions": ["前端", "ui", "界面"]
                    },
                    "validation_rules": []
                }
            ]
        }
        role_manager.load_roles(role_data)
        
        router = TaskRouter(role_manager)
        
        # Create frontend task assigned to backend role
        task = Task(
            id="task1",
            description="开发一个用户登录页面，包含用户名密码输入框",
            category="frontend"
        )
        
        assignment = router.assign_task(task, target_role_id="backend_engineer")
        
        assert assignment.status == "rejected"
        assert assignment.assigned_role == "backend_engineer"
        assert task.status == "rejected"
        assert task.rejection_reason is not None
        assert "cannot handle" in assignment.feedback.lower() or "not within" in assignment.feedback.lower()
    
    def test_assign_task_with_suggestion(self, temp_workspace):
        """Test task assignment with role suggestion on rejection."""
        role_manager = RoleManager()
        
        # Load skill library
        skill_data = {
            "schema_version": "1.0",
            "skills": [
                {
                    "id": "frontend_skill",
                    "name": "Frontend Development",
                    "description": "Develop frontend components",
                    "category": "frontend"
                },
                {
                    "id": "backend_skill",
                    "name": "Backend Development",
                    "description": "Develop backend APIs",
                    "category": "backend"
                }
            ]
        }
        role_manager.load_skill_library(skill_data)
        
        # Load roles
        role_data = {
            "schema_version": "1.0",
            "roles": [
                {
                    "id": "backend_engineer",
                    "name": "Backend Engineer",
                    "description": "Backend developer",
                    "skills": ["backend_skill"],
                    "domain": "backend",
                    "responsibility": "开发API和服务",
                    "constraints": {
                        "forbidden_actions": ["前端", "ui", "界面"]
                    },
                    "validation_rules": []
                },
                {
                    "id": "frontend_engineer",
                    "name": "Frontend Engineer",
                    "description": "Frontend developer",
                    "skills": ["frontend_skill"],
                    "domain": "frontend",
                    "responsibility": "开发用户界面和前端组件",
                    "constraints": {},
                    "validation_rules": []
                }
            ]
        }
        role_manager.load_roles(role_data)
        
        router = TaskRouter(role_manager)
        
        # Create frontend task assigned to backend role
        task = Task(
            id="task1",
            description="开发一个用户登录页面",
            category="frontend"
        )
        
        assignment = router.assign_task(task, target_role_id="backend_engineer")
        
        assert assignment.status == "rejected"
        # Should suggest frontend_engineer
        assert assignment.suggested_role == "frontend_engineer"
        assert task.reassigned_to == "frontend_engineer"
    
    def test_get_task_history(self, temp_workspace):
        """Test getting task history."""
        role_manager = RoleManager()
        router = TaskRouter(role_manager)
        
        # Load minimal setup
        skill_data = {
            "schema_version": "1.0",
            "skills": [
                {
                    "id": "test_skill",
                    "name": "Test Skill",
                    "description": "Test",
                    "category": "general"
                }
            ]
        }
        role_manager.load_skill_library(skill_data)
        
        role_data = {
            "schema_version": "1.0",
            "roles": [
                {
                    "id": "test_role",
                    "name": "Test Role",
                    "description": "Test",
                    "skills": ["test_skill"],
                    "domain": "general",
                    "responsibility": "Test responsibility",
                    "constraints": {},
                    "validation_rules": []
                }
            ]
        }
        role_manager.load_roles(role_data)
        
        task = Task(id="task1", description="Test task", category="general")
        router.assign_task(task, target_role_id="test_role")
        
        history = router.get_task_history()
        assert len(history) == 1
        assert history[0].task_id == "task1"
        
        # Filter by role
        history = router.get_task_history(role_id="test_role")
        assert len(history) == 1
        
        history = router.get_task_history(role_id="nonexistent")
        assert len(history) == 0
    
    def test_get_rejection_rate(self, temp_workspace):
        """Test getting rejection rate."""
        role_manager = RoleManager()
        router = TaskRouter(role_manager)
        
        # Load setup with two roles
        skill_data = {
            "schema_version": "1.0",
            "skills": [
                {
                    "id": "frontend_skill",
                    "name": "Frontend",
                    "description": "Frontend",
                    "category": "frontend"
                },
                {
                    "id": "backend_skill",
                    "name": "Backend",
                    "description": "Backend",
                    "category": "backend"
                }
            ]
        }
        role_manager.load_skill_library(skill_data)
        
        role_data = {
            "schema_version": "1.0",
            "roles": [
                {
                    "id": "frontend_engineer",
                    "name": "Frontend",
                    "description": "Frontend",
                    "skills": ["frontend_skill"],
                    "domain": "frontend",
                    "responsibility": "前端开发",
                    "constraints": {},
                    "validation_rules": []
                },
                {
                    "id": "backend_engineer",
                    "name": "Backend",
                    "description": "Backend",
                    "skills": ["backend_skill"],
                    "domain": "backend",
                    "responsibility": "后端开发",
                    "constraints": {"forbidden_actions": ["前端"]},
                    "validation_rules": []
                }
            ]
        }
        role_manager.load_roles(role_data)
        
        # Assign frontend task to backend (should reject)
        task1 = Task(id="task1", description="开发前端页面", category="frontend")
        router.assign_task(task1, target_role_id="backend_engineer")
        
        # Assign backend task to backend (should accept)
        task2 = Task(id="task2", description="开发API", category="backend")
        router.assign_task(task2, target_role_id="backend_engineer")
        
        rejection_rate = router.get_rejection_rate("backend_engineer")
        assert rejection_rate == 0.5  # 1 rejected out of 2
        
        rejection_rate = router.get_rejection_rate("frontend_engineer")
        assert rejection_rate == 0.0  # No assignments

