"""
Skill selector for choosing appropriate skills based on task and context.
Following Single Responsibility Principle - handles skill selection only.
"""

from typing import Dict, List, Optional, Any, Tuple
from difflib import SequenceMatcher

from .models import Skill, Role, SkillExecution
from .execution_tracker import ExecutionTracker


class SkillSelector:
    """Selects appropriate skills based on task description and context"""
    
    def __init__(self, engine: 'WorkflowEngine', execution_tracker: Optional[ExecutionTracker] = None):
        self.engine = engine
        self.execution_tracker = execution_tracker
    
    def select_skill(
        self,
        task_description: str,
        role: Role,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Skill]:
        """
        Select the most appropriate skill for a given task.
        
        Selection logic:
        1. Filter skills by role constraints
        2. Match skills by task description
        3. Score skills by historical success rate
        4. Check prerequisites
        """
        available_skills = self._get_available_skills(role)
        if not available_skills:
            return None
        
        # Match skills by task description (now returns scored list)
        matched_skills_with_scores = self._match_skills_by_task(task_description, available_skills)
        if not matched_skills_with_scores:
            return None
        
        # Extract skills from matched results
        matched_skills = [skill for skill, _ in matched_skills_with_scores]
        
        # Score skills based on history and context
        scored_skills = self._score_skills(matched_skills, context=context)
        if not scored_skills:
            return None
        
        # Check prerequisites for top candidates
        for skill, score in scored_skills:
            if self._check_prerequisites(skill, context or {}):
                return skill
        
        # If no skill passes prerequisites, return highest scored one anyway
        return scored_skills[0][0] if scored_skills else None
    
    def select_skills(
        self,
        task_description: str,
        role: Role,
        context: Optional[Dict[str, Any]] = None,
        max_results: int = 5
    ) -> List[Tuple[Skill, float]]:
        """
        Select multiple candidate skills for a given task, sorted by relevance.
        
        Returns a list of (skill, score) tuples ordered by relevance score.
        Useful for skill combination recommendations or when multiple skills
        might be needed to complete a task.
        
        Args:
            task_description: Description of the task
            role: Role that will execute the skills
            context: Optional context information
            max_results: Maximum number of skills to return
            
        Returns:
            List of (skill, score) tuples, sorted by score descending
        """
        available_skills = self._get_available_skills(role)
        if not available_skills:
            return []
        
        # Match skills by task description (returns scored list)
        matched_skills_with_scores = self._match_skills_by_task(task_description, available_skills)
        if not matched_skills_with_scores:
            return []
        
        # Extract skills from matched results
        matched_skills = [skill for skill, _ in matched_skills_with_scores]
        
        # Score skills based on history and context
        scored_skills = self._score_skills(matched_skills, context=context)
        if not scored_skills:
            return []
        
        # Filter by prerequisites and return top N
        result = []
        for skill, score in scored_skills:
            if self._check_prerequisites(skill, context or {}):
                result.append((skill, score))
                if len(result) >= max_results:
                    break
        
        # If we don't have enough skills that pass prerequisites, add others anyway
        if len(result) < max_results:
            for skill, score in scored_skills:
                if (skill, score) not in result:
                    result.append((skill, score))
                    if len(result) >= max_results:
                        break
        
        return result
    
    def _get_available_skills(self, role: Role) -> List[Skill]:
        """Get skills available to a role"""
        if not self.engine.role_manager.skill_library:
            return []
        
        skills = []
        for req in role.required_skills:
            # Handle both SkillRequirement objects and dicts
            if isinstance(req, dict):
                skill_id = req.get('skill_id')
            else:
                skill_id = req.skill_id
            
            if not skill_id or not self.engine.role_manager.skill_library:
                continue
            
            skill = self.engine.role_manager.skill_library.get(skill_id)
            if skill:
                skills.append(skill)
        return skills
    
    def _match_skills_by_task(self, task: str, skills: List[Skill]) -> List[Tuple[Skill, float]]:
        """
        Match skills based on task description using semantic similarity.
        
        Returns list of (skill, score) tuples sorted by relevance score.
        Score ranges from 0.0 to 1.0, where 1.0 is perfect match.
        """
        if not task or not skills:
            return [(skill, 0.0) for skill in skills]
        
        task_lower = task.lower()
        task_words = set(word for word in task_lower.split() if len(word) > 2)
        
        matched_scores = []
        
        for skill in skills:
            score = 0.0
            
            # 1. Description similarity (weight: 0.5)
            skill_desc_lower = skill.description.lower()
            desc_similarity = SequenceMatcher(None, task_lower, skill_desc_lower).ratio()
            score += desc_similarity * 0.5
            
            # 2. Dimension matching (weight: 0.3)
            dimension_matches = 0
            for dim in skill.dimensions:
                dim_lower = dim.lower()
                # Check if dimension appears in task
                if dim_lower in task_lower:
                    dimension_matches += 1
                # Also check word-level matching
                dim_words = set(dim_lower.split('_'))
                if task_words & dim_words:
                    dimension_matches += 0.5
            
            if skill.dimensions:
                dimension_score = min(1.0, dimension_matches / len(skill.dimensions))
            else:
                dimension_score = 0.0
            score += dimension_score * 0.3
            
            # 3. Keyword matching in description (weight: 0.2)
            skill_words = set(word for word in skill_desc_lower.split() if len(word) > 2)
            if task_words and skill_words:
                keyword_overlap = len(task_words & skill_words) / len(task_words | skill_words)
                score += keyword_overlap * 0.2
            
            matched_scores.append((skill, score))
        
        # Sort by score descending
        matched_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Filter out very low scores (below 0.1) unless no matches found
        filtered = [ms for ms in matched_scores if ms[1] >= 0.1]
        if not filtered and matched_scores:
            # Fallback: return all skills with their scores
            return matched_scores
        
        return filtered if filtered else matched_scores
    
    def _score_skills(
        self,
        skills: List[Skill],
        history: Optional[List[SkillExecution]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Skill, float]]:
        """
        Score skills based on multiple factors:
        - Historical performance (success rate, execution time)
        - Context matching (project type, tech stack, current stage)
        - Skill level requirements matching
        - Dependency satisfaction
        """
        context = context or {}
        scored = []
        
        for skill in skills:
            score = 0.0
            weights = {
                'history': 0.4,
                'context': 0.3,
                'level_match': 0.2,
                'dependencies': 0.1
            }
            
            # 1. Historical performance (weight: 0.4)
            history_score = 0.5  # Default neutral score
            if self.execution_tracker:
                success_rate = self.execution_tracker.get_success_rate(skill.id)
                avg_time = self.execution_tracker.get_avg_execution_time(skill.id)
                execution_count = self.execution_tracker.get_total_executions(skill.id)
                
                if execution_count > 0:
                    history_score = success_rate
                    # Boost for skills with good history
                    if success_rate > 0.7:
                        history_score += 0.1
                    # Penalize for very slow execution
                    if avg_time > 10.0:
                        history_score -= 0.1
                else:
                    # New skills get neutral score
                    history_score = 0.5
            
            score += history_score * weights['history']
            
            # 2. Context matching (weight: 0.3)
            context_score = self._calculate_context_match(skill, context)
            score += context_score * weights['context']
            
            # 3. Skill level requirements matching (weight: 0.2)
            level_score = self._calculate_level_match(skill, context)
            score += level_score * weights['level_match']
            
            # 4. Dependency satisfaction (weight: 0.1)
            dep_score = 1.0 if self._check_prerequisites(skill, context) else 0.5
            score += dep_score * weights['dependencies']
            
            scored.append((skill, max(0.0, min(1.0, score))))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
    
    def _calculate_context_match(self, skill: Skill, context: Dict[str, Any]) -> float:
        """Calculate how well skill matches the current context"""
        score = 0.5  # Default neutral score
        
        # Check project type matching
        project_type = context.get('project_type', '')
        if project_type:
            # Skills can have metadata indicating preferred project types
            if skill.metadata and 'project_types' in skill.metadata:
                preferred_types = skill.metadata['project_types']
                if isinstance(preferred_types, list):
                    if project_type in preferred_types:
                        score += 0.2
                    elif any(pt in project_type for pt in preferred_types):
                        score += 0.1
        
        # Check tech stack matching
        tech_stack = context.get('tech_stack', [])
        if tech_stack and isinstance(tech_stack, list):
            # Check if skill tools match tech stack
            if skill.tools:
                matching_tools = sum(1 for tool in skill.tools if tool in tech_stack)
                if matching_tools > 0:
                    score += min(0.2, matching_tools * 0.1)
        
        # Check current stage matching
        current_stage = context.get('current_stage', '')
        if current_stage:
            # Skills can indicate preferred stages
            if skill.metadata and 'preferred_stages' in skill.metadata:
                preferred_stages = skill.metadata['preferred_stages']
                if isinstance(preferred_stages, list) and current_stage in preferred_stages:
                    score += 0.1
        
        return min(1.0, score)
    
    def _calculate_level_match(self, skill: Skill, context: Dict[str, Any]) -> float:
        """Calculate how well skill level matches requirements"""
        # If context specifies required level, check match
        required_level = context.get('required_level')
        if required_level and isinstance(required_level, int):
            # Assume skill has levels 1-3, higher is better
            # This is a simplified calculation
            if hasattr(skill, 'levels') and skill.levels:
                max_level = max(skill.levels.keys()) if isinstance(skill.levels, dict) else 3
                if required_level <= max_level:
                    return 1.0
                else:
                    # Penalize if skill level is too low
                    return max(0.0, 1.0 - (required_level - max_level) * 0.2)
        
        return 0.5  # Neutral if no level requirement
    
    def _check_prerequisites(self, skill: Skill, context: Dict[str, Any]) -> bool:
        """Check if skill prerequisites are met"""
        # Check if skill has prerequisites defined in metadata
        if skill.metadata and 'prerequisites' in skill.metadata:
            prereqs = skill.metadata['prerequisites']
            if isinstance(prereqs, list):
                # Check if prerequisite skills have been executed successfully
                if self.execution_tracker:
                    for prereq_skill_id in prereqs:
                        history = self.execution_tracker.get_skill_history(prereq_skill_id)
                        if not any(e.status == "success" for e in history):
                            return False
        
        # Check if required context is available
        if skill.input_schema:
            required_fields = skill.input_schema.get('required', [])
            for field in required_fields:
                if field not in context:
                    return False
        
        return True


class RetryHandler:
    """Handles retry logic for skill execution failures"""
    
    def __init__(self, execution_tracker: Optional[ExecutionTracker] = None):
        self.execution_tracker = execution_tracker
    
    def should_retry(
        self,
        error: Exception,
        skill: Skill,
        execution: SkillExecution
    ) -> bool:
        """Determine if a skill execution should be retried"""
        if not skill.error_handling:
            return False
        
        error_config = skill.error_handling
        max_retries = error_config.get('max_retries', 0)
        
        # Check if max retries exceeded
        if execution.retry_count >= max_retries:
            return False
        
        # Check error type
        error_type = error_config.get('retry_on', [])
        if isinstance(error_type, list):
            error_name = type(error).__name__
            if error_name not in error_type:
                return False
        
        return True

