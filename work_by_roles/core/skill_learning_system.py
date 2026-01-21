"""
Skill Learning System for execution pattern analysis and skill optimization.
Following Single Responsibility Principle - handles analysis of execution history and optimization recommendations only.
"""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from .models import Skill, SkillExecution
from .execution_tracker import ExecutionTracker


@dataclass
class SkillMetrics:
    """Quantitative performance metrics for a skill"""
    skill_id: str
    total_executions: int
    success_rate: float
    avg_execution_time: float
    error_distribution: Dict[str, int]
    reliability_score: float  # Weighted score based on success and consistency
    trend: str  # "improving", "stable", "declining"


@dataclass
class PatternAnalysis:
    """Analysis of execution patterns for a skill"""
    skill_id: str
    common_inputs: List[Dict[str, Any]]
    success_patterns: List[str]
    failure_patterns: List[str]
    context_affinities: Dict[str, float]  # How well skill performs in different contexts (stage, role)


@dataclass
class SkillImprovement:
    """Recommended improvement for a skill"""
    type: str  # "prompt", "parameters", "constraint", "documentation"
    description: str
    reasoning: str
    priority: int  # 1-5, higher is more critical
    suggested_change: Optional[Dict[str, Any]] = None


class SkillLearningSystem:
    """
    Analyzes skill execution data to provide insights and optimization suggestions.
    
    This system helps in:
    1. Quantifying skill performance (success rate, time, errors).
    2. Identifying patterns that lead to success or failure.
    3. Suggesting improvements to skill definitions, prompts, or constraints.
    4. Monitoring performance trends over time.
    """
    
    def __init__(self, execution_tracker: ExecutionTracker):
        """
        Initialize SkillLearningSystem.
        
        Args:
            execution_tracker: The tracker containing execution history
        """
        self.execution_tracker = execution_tracker
        
    def get_skill_metrics(self, skill_id: str, days: int = 30) -> SkillMetrics:
        """
        Calculate performance metrics for a skill.
        
        Args:
            skill_id: ID of the skill
            days: Number of recent days to include in trend analysis
            
        Returns:
            SkillMetrics object
        """
        history = self.execution_tracker.get_skill_history(skill_id)
        if not history:
            return SkillMetrics(
                skill_id=skill_id, total_executions=0, success_rate=0.0, 
                avg_execution_time=0.0, error_distribution={}, reliability_score=0.0, trend="unknown"
            )
            
        total = len(history)
        success_rate = self.execution_tracker.get_success_rate(skill_id)
        avg_time = self.execution_tracker.get_avg_execution_time(skill_id)
        
        # Error distribution
        errors = {}
        for e in history:
            if e.status != "success" and e.error_type:
                errors[e.error_type] = errors.get(e.error_type, 0) + 1
                
        # Trend analysis (compare recent vs older)
        cutoff = datetime.now() - timedelta(days=days/2)
        recent = [e for e in history if e.timestamp > cutoff]
        older = [e for e in history if e.timestamp <= cutoff]
        
        trend = "stable"
        if recent and older:
            recent_sr = sum(1 for e in recent if e.status == "success") / len(recent)
            older_sr = sum(1 for e in older if e.status == "success") / len(older)
            if recent_sr > older_sr + 0.1:
                trend = "improving"
            elif recent_sr < older_sr - 0.1:
                trend = "declining"
                
        # Reliability score (simple version)
        reliability = success_rate * (1.0 - min(1.0, avg_time / 60.0))
        
        return SkillMetrics(
            skill_id=skill_id,
            total_executions=total,
            success_rate=success_rate,
            avg_execution_time=avg_time,
            error_distribution=errors,
            reliability_score=reliability,
            trend=trend
        )
        
    def analyze_patterns(self, skill_id: str) -> PatternAnalysis:
        """
        Identify patterns in execution data.
        
        Args:
            skill_id: ID of the skill
            
        Returns:
            PatternAnalysis object
        """
        history = self.execution_tracker.get_skill_history(skill_id)
        
        # In a real implementation, this would use more advanced data mining
        # or LLM-based pattern recognition.
        
        # stage/role affinity
        affinities = {}
        stage_success = {}
        stage_total = {}
        
        for e in history:
            if e.stage_id:
                stage_total[e.stage_id] = stage_total.get(e.stage_id, 0) + 1
                if e.status == "success":
                    stage_success[e.stage_id] = stage_success.get(e.stage_id, 0) + 1
                    
        for stage_id, total in stage_total.items():
            affinities[f"stage:{stage_id}"] = stage_success.get(stage_id, 0) / total
            
        return PatternAnalysis(
            skill_id=skill_id,
            common_inputs=[], # Simplified for now
            success_patterns=[],
            failure_patterns=[],
            context_affinities=affinities
        )
        
    def suggest_improvements(self, skill: Skill) -> List[SkillImprovement]:
        """
        Generate suggestions for skill optimization.
        
        Args:
            skill: The Skill object to improve
            
        Returns:
            List of SkillImprovement suggestions
        """
        metrics = self.get_skill_metrics(skill.id)
        history = self.execution_tracker.get_skill_history(skill.id)
        suggestions = []
        
        # High failure rate suggestion
        if metrics.success_rate < 0.7 and metrics.total_executions > 5:
            suggestions.append(SkillImprovement(
                type="prompt",
                description="Refine instruction template to handle common failure modes",
                reasoning=f"Skill '{skill.id}' has a success rate of only {metrics.success_rate:.1%}",
                priority=4
            ))
            
        # Slow execution suggestion
        if metrics.avg_execution_time > 30.0:
            suggestions.append(SkillImprovement(
                type="parameters",
                description="Optimize parameters or split skill for performance",
                reasoning=f"Average execution time is {metrics.avg_execution_time:.1f}s, which is relatively slow",
                priority=2
            ))
            
        # Error-specific suggestions
        if "timeout" in metrics.error_distribution:
            suggestions.append(SkillImprovement(
                type="constraint",
                description="Increase timeout threshold or optimize processing",
                reasoning="Timeouts represent a significant portion of failures",
                priority=3
            ))
            
        return suggestions
