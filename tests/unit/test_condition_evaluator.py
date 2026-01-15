"""
Unit tests for ConditionEvaluator.
"""
import pytest

from work_by_roles.core.condition_evaluator import ConditionEvaluator


class TestConditionEvaluator:
    """Test ConditionEvaluator functionality."""
    
    def test_evaluate_simple_condition(self):
        """Test evaluating a simple condition."""
        step_outputs = {"step1": {"result": {"status": "success"}}}
        inputs = {}
        
        evaluator = ConditionEvaluator(step_outputs, inputs)
        
        result = evaluator.evaluate("{{step.step1.result.status}} == 'success'")
        
        assert result is True
    
    def test_evaluate_false_condition(self):
        """Test evaluating a false condition."""
        step_outputs = {"step1": {"result": {"status": "failed"}}}
        inputs = {}
        
        evaluator = ConditionEvaluator(step_outputs, inputs)
        
        result = evaluator.evaluate("{{step.step1.result.status}} == 'success'")
        
        assert result is False
    
    def test_evaluate_with_inputs(self):
        """Test evaluating condition with inputs."""
        step_outputs = {}
        inputs = {"value": 10}
        
        evaluator = ConditionEvaluator(step_outputs, inputs)
        
        result = evaluator.evaluate("{{inputs.value}} > 5")
        
        assert result is True
    
    def test_evaluate_complex_condition(self):
        """Test evaluating a complex condition."""
        step_outputs = {
            "step1": {"result": {"count": 5}},
            "step2": {"result": {"count": 3}}
        }
        inputs = {}
        
        evaluator = ConditionEvaluator(step_outputs, inputs)
        
        result = evaluator.evaluate("{{step.step1.result.count}} > {{step.step2.result.count}}")
        
        assert result is True

