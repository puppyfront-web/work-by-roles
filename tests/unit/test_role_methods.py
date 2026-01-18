"""
Unit tests for Role methods (can_handle_task, evaluate_task, match_score).
"""
import pytest

from work_by_roles.core.models import Role, Task, Skill
from work_by_roles.core.role_manager import RoleManager


class TestRoleMethods:
    """Test Role task handling methods."""
    
    def test_can_handle_task_domain_match(self, temp_workspace):
        """Test can_handle_task with domain matching."""
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
        
        role = Role(
            id="frontend_engineer",
            name="Frontend Engineer",
            description="Frontend developer",
            skills=["frontend_skill"],
            domain="frontend",
            responsibility="开发用户界面",
            constraints={},
            validation_rules=[]
        )
        
        # Frontend task should match
        assert role.can_handle_task("开发一个React组件", role_manager) == True
        
        # Backend task should not match
        assert role.can_handle_task("开发一个REST API", role_manager) == False
    
    def test_can_handle_task_responsibility_match(self, temp_workspace):
        """Test can_handle_task with responsibility matching."""
        role_manager = RoleManager()
        
        role = Role(
            id="test_role",
            name="Test Role",
            description="Test",
            skills=[],
            domain="analysis",  # 使用特定领域，不是general
            responsibility="分析需求和设计架构",
            constraints={},
            validation_rules=[]
        )
        
        # Task matching responsibility
        assert role.can_handle_task("分析用户需求并设计系统架构", role_manager) == True
        
        # Task not matching responsibility - 添加约束来明确拒绝
        role_with_constraint = Role(
            id="test_role",
            name="Test Role",
            description="Test",
            skills=[],
            domain="analysis",
            responsibility="分析需求和设计架构",
            constraints={"forbidden_actions": ["编写代码", "实现功能"]},
            validation_rules=[]
        )
        assert role_with_constraint.can_handle_task("编写代码实现功能", role_manager) == False
    
    def test_can_handle_task_constraints(self, temp_workspace):
        """Test can_handle_task with constraints."""
        role_manager = RoleManager()
        
        role = Role(
            id="backend_engineer",
            name="Backend Engineer",
            description="Backend developer",
            skills=[],
            domain="backend",
            responsibility="开发API",
            constraints={
                "forbidden_actions": ["前端", "ui", "界面"]
            },
            validation_rules=[]
        )
        
        # Task with forbidden action should not match
        assert role.can_handle_task("开发前端界面", role_manager) == False
        
        # Task without forbidden action should match
        assert role.can_handle_task("开发REST API", role_manager) == True
    
    def test_evaluate_task_accepted(self, temp_workspace):
        """Test evaluate_task with accepted task."""
        role_manager = RoleManager()
        
        role = Role(
            id="frontend_engineer",
            name="Frontend Engineer",
            description="Frontend developer",
            skills=[],
            domain="frontend",
            responsibility="开发用户界面",
            constraints={},
            validation_rules=[]
        )
        
        task = Task(
            id="task1",
            description="开发一个React组件",
            category="frontend"
        )
        
        can_handle, feedback = role.evaluate_task(task, role_manager)
        
        assert can_handle == True
        assert "accepts" in feedback.lower() or "✅" in feedback
    
    def test_evaluate_task_rejected(self, temp_workspace):
        """Test evaluate_task with rejected task."""
        role_manager = RoleManager()
        
        role = Role(
            id="backend_engineer",
            name="Backend Engineer",
            description="Backend developer",
            skills=[],
            domain="backend",
            responsibility="开发API",
            constraints={
                "forbidden_actions": ["前端"]
            },
            validation_rules=[]
        )
        
        task = Task(
            id="task1",
            description="开发前端页面",
            category="frontend"
        )
        
        can_handle, feedback = role.evaluate_task(task, role_manager)
        
        assert can_handle == False
        assert "cannot handle" in feedback.lower() or "❌" in feedback or "not within" in feedback.lower()
    
    def test_match_score(self, temp_workspace):
        """Test match_score calculation."""
        role_manager = RoleManager()
        
        # Load skill library
        skill_data = {
            "schema_version": "1.0",
            "skills": [
                {
                    "id": "frontend_skill",
                    "name": "React Development",
                    "description": "Develop React components",
                    "category": "frontend"
                }
            ]
        }
        role_manager.load_skill_library(skill_data)
        
        role = Role(
            id="frontend_engineer",
            name="Frontend Engineer",
            description="Frontend developer",
            skills=["frontend_skill"],
            domain="frontend",
            responsibility="开发用户界面和React组件",
            constraints={},
            validation_rules=[]
        )
        
        # Perfect match
        score = role.match_score("开发React组件", "frontend", role_manager)
        assert score > 0.5
        
        # Domain match
        score = role.match_score("开发前端页面", "frontend", role_manager)
        assert score > 0.3
        
        # No match
        score = role.match_score("开发后端API", "backend", role_manager)
        assert score < 0.5

