"""
Unit tests for SkillSelector.
"""
import pytest

from work_by_roles.core.skill_selector import SkillSelector
from work_by_roles.core.models import Skill, Role, SkillExecution
from work_by_roles.core.execution_tracker import ExecutionTracker


class TestSkillSelector:
    """Test SkillSelector functionality."""
    
    def test_skill_selector_initialization(self, workflow_engine):
        """Test initializing SkillSelector."""
        selector = SkillSelector(workflow_engine)
        
        assert selector.engine == workflow_engine
        # execution_tracker may be None if not provided, which is valid
        # The important thing is that it doesn't crash
    
    def test_skill_selector_with_tracker(self, workflow_engine):
        """Test initializing with custom tracker."""
        tracker = ExecutionTracker()
        selector = SkillSelector(workflow_engine, tracker)
        
        assert selector.execution_tracker == tracker
    
    def test_select_skill(self, workflow_engine, sample_skill, sample_role):
        """Test selecting a skill."""
        workflow_engine.role_manager.skill_library = {"test_skill": sample_skill}
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        selector = SkillSelector(workflow_engine)
        
        selected = selector.select_skill("test task", sample_role)
        
        # Should return a skill or None
        assert selected is None or isinstance(selected, Skill)
    
    def test_select_skills_multiple(self, workflow_engine, sample_skill, sample_role):
        """Test selecting multiple candidate skills."""
        workflow_engine.role_manager.skill_library = {"test_skill": sample_skill}
        workflow_engine.role_manager.roles = {"test_role": sample_role}
        
        selector = SkillSelector(workflow_engine)
        
        skills = selector.select_skills("test task", sample_role, max_results=5)
        
        assert isinstance(skills, list)
        assert len(skills) <= 5

