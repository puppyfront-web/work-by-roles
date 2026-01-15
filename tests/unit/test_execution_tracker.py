"""
Unit tests for ExecutionTracker.
"""
import pytest
from datetime import datetime

from work_by_roles.core.execution_tracker import ExecutionTracker
from work_by_roles.core.models import SkillExecution
from work_by_roles.core.enums import SkillErrorType


class TestExecutionTracker:
    """Test ExecutionTracker functionality."""
    
    def test_tracker_initialization(self):
        """Test initializing ExecutionTracker."""
        tracker = ExecutionTracker()
        
        assert tracker.executions == []
    
    def test_record_execution(self):
        """Test recording an execution."""
        tracker = ExecutionTracker()
        
        execution = SkillExecution(
            skill_id="test_skill",
            input={"test": "input"},
            output={"test": "output"},
            status="success",
            execution_time=1.5
        )
        
        tracker.record_execution(execution)
        
        assert len(tracker.executions) == 1
        assert tracker.executions[0] == execution
    
    def test_get_success_rate(self):
        """Test getting success rate."""
        tracker = ExecutionTracker()
        
        # Record successful executions
        for i in range(3):
            tracker.record_execution(SkillExecution(
                skill_id="test_skill",
                input={},
                output={},
                status="success",
                execution_time=1.0
            ))
        
        # Record failed execution
        tracker.record_execution(SkillExecution(
            skill_id="test_skill",
            input={},
            output=None,
            status="failed",
            execution_time=0.5
        ))
        
        success_rate = tracker.get_success_rate("test_skill")
        assert success_rate == 0.75  # 3 out of 4
    
    def test_get_avg_execution_time(self):
        """Test getting average execution time."""
        tracker = ExecutionTracker()
        
        tracker.record_execution(SkillExecution(
            skill_id="test_skill",
            input={},
            output={},
            status="success",
            execution_time=2.0
        ))
        
        tracker.record_execution(SkillExecution(
            skill_id="test_skill",
            input={},
            output={},
            status="success",
            execution_time=4.0
        ))
        
        avg_time = tracker.get_avg_execution_time("test_skill")
        assert avg_time == 3.0
    
    def test_get_total_executions(self):
        """Test getting total execution count."""
        tracker = ExecutionTracker()
        
        for i in range(5):
            tracker.record_execution(SkillExecution(
                skill_id="test_skill",
                input={},
                output={},
                status="success",
                execution_time=1.0
            ))
        
        count = tracker.get_total_executions("test_skill")
        assert count == 5

