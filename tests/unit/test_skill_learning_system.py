import pytest
from unittest.mock import MagicMock
from datetime import datetime
from work_by_roles.core.skill_learning_system import SkillLearningSystem
from work_by_roles.core.models import SkillExecution, Skill

def test_skill_metrics():
    tracker = MagicMock()
    # Mock history
    e1 = SkillExecution(skill_id="s1", input={}, output={}, status="success", execution_time=1.0)
    e2 = SkillExecution(skill_id="s1", input={}, output={}, status="failed", error_type="timeout", execution_time=5.0)
    
    tracker.get_skill_history.return_value = [e1, e2]
    tracker.get_success_rate.return_value = 0.5
    tracker.get_avg_execution_time.return_value = 3.0
    
    ls = SkillLearningSystem(tracker)
    metrics = ls.get_skill_metrics("s1")
    
    assert metrics.total_executions == 2
    assert metrics.success_rate == 0.5
    assert metrics.error_distribution["timeout"] == 1

def test_suggest_improvements():
    tracker = MagicMock()
    ls = SkillLearningSystem(tracker)
    
    # Mock bad performance
    tracker.get_success_rate.return_value = 0.4
    tracker.get_avg_execution_time.return_value = 40.0
    
    # Create real execution objects with timestamps
    history = []
    for i in range(10):
        history.append(SkillExecution(
            skill_id="s1", input={}, output={}, status="failed", 
            execution_time=40.0, timestamp=datetime.now()
        ))
    tracker.get_skill_history.return_value = history
    
    skill = Skill(id="s1", name="S1", description="D", category="C")
    suggestions = ls.suggest_improvements(skill)
    
    assert len(suggestions) >= 2
    types = [s.type for s in suggestions]
    assert "prompt" in types
    assert "parameters" in types
