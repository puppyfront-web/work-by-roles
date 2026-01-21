"""
Skill Composition Engine for smart skill combination and compound skill creation.
Following Single Responsibility Principle - handles skill composition logic only.
"""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from .models import Skill, SkillDependency
from .skill_learning_system import SkillLearningSystem


@dataclass
class SkillComposition:
    """A recommended combination of skills for a task"""
    skill_ids: List[str]
    rationale: str
    relevance_score: float
    expected_benefits: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of skill composition validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    resolved_dependencies: List[str] = field(default_factory=list)


class SkillCompositionEngine:
    """
    Manages the creation and recommendation of skill combinations (compound skills).
    
    This engine helps in:
    1. Recommending multiple skills that work well together for a specific goal.
    2. Creating new "compound" skills from existing ones.
    3. Validating that a set of skills is compatible and dependencies are met.
    4. Predicting the effectiveness of a skill combination using the learning system.
    """
    
    def __init__(self, skill_library: Dict[str, Skill], learning_system: Optional[SkillLearningSystem] = None):
        """
        Initialize SkillCompositionEngine.
        
        Args:
            skill_library: The library of available skills
            learning_system: Optional system for performance data
        """
        self.skill_library = skill_library
        self.learning_system = learning_system
        
    def recommend_composition(self, task_description: str) -> List[SkillComposition]:
        """
        Suggest combinations of skills for a given task.
        
        Args:
            task_description: Description of the goal
            
        Returns:
            List of SkillComposition recommendations
        """
        # In a real implementation, this would use semantic search or LLM
        # to find matching skills and analyze their synergies.
        
        # Simplified logic for now:
        recommendations = []
        
        # Example recommendation
        recommendations.append(SkillComposition(
            skill_ids=[], # Would contain real IDs
            rationale="Combination of analysis and design skills recommended for this complex task",
            relevance_score=0.8,
            expected_benefits=["Clearer requirements", "Aligned architecture"]
        ))
        
        return recommendations
        
    def create_compound_skill(self, skill_ids: List[str], name: str, description: str) -> Skill:
        """
        Combine multiple skills into a single new compound skill.
        
        Args:
            skill_ids: List of skills to combine
            name: Name for the new skill
            description: Description for the new skill
            
        Returns:
            A new Skill object representing the combination
        """
        # Validate skills exist
        for sid in skill_ids:
            if sid not in self.skill_library:
                raise ValueError(f"Skill '{sid}' not found in library")
                
        # Merge metadata, tools, and constraints
        all_tools = set()
        all_constraints = []
        combined_dependencies = []
        
        for sid in skill_ids:
            s = self.skill_library[sid]
            all_tools.update(s.tools)
            all_constraints.extend(s.constraints)
            # Add dependency on original skills
            combined_dependencies.append(SkillDependency(skill_id=sid))
            
        # Create new ID
        compound_id = f"compound_{'_'.join(skill_ids)[:30]}"
        
        return Skill(
            id=compound_id,
            name=name,
            description=description,
            category="compound",
            tools=list(all_tools),
            constraints=list(set(all_constraints)),
            dependencies=combined_dependencies,
            skill_type="hybrid",
            metadata={"is_compound": True, "original_skills": skill_ids}
        )
        
    def validate_composition(self, skill_ids: List[str]) -> ValidationResult:
        """
        Validate that a set of skills can work together.
        
        Args:
            skill_ids: List of skill IDs to validate
            
        Returns:
            ValidationResult object
        """
        errors = []
        warnings = []
        resolved = []
        
        # Check existence
        for sid in skill_ids:
            if sid not in self.skill_library:
                errors.append(f"Skill '{sid}' not found")
                continue
            resolved.append(sid)
            
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
            
        # Check dependencies
        for sid in skill_ids:
            skill = self.skill_library[sid]
            for dep in skill.dependencies:
                if not dep.optional and dep.skill_id not in resolved:
                    # In a real system, we'd check version constraints too
                    errors.append(f"Skill '{sid}' requires '{dep.skill_id}', which is missing")
                    
        # Synergetic checks using learning system
        if self.learning_system:
            for sid in skill_ids:
                metrics = self.learning_system.get_skill_metrics(sid)
                if metrics.success_rate < 0.5:
                    warnings.append(f"Skill '{sid}' has historically low success rate ({metrics.success_rate:.1%})")
                    
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            resolved_dependencies=resolved
        )
