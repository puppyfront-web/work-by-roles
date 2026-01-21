"""
Skill Version Manager for version tracking and compatibility checking.
Following Single Responsibility Principle - handles skill versioning and dependency resolution only.
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from .models import Skill, SkillDependency
from .exceptions import ValidationError


@dataclass
class CompatibilityResult:
    """Result of compatibility check"""
    compatible: bool
    reason: Optional[str] = None
    issues: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)


@dataclass
class UpgradeResult:
    """Result of skill upgrade operation"""
    success: bool
    from_version: str
    to_version: str
    changelog: List[str] = field(default_factory=list)
    breaking_changes: bool = False
    error: Optional[str] = None


class SkillVersionManager:
    """
    Manages skill versions and dependency resolution.
    
    This class handles:
    1. Compatibility checking between skill versions.
    2. Dependency resolution for skill bundles or roles.
    3. Managing skill upgrade paths.
    4. Retrieving version history and changelogs.
    """
    
    def __init__(self, skill_library: Dict[str, Skill]):
        """
        Initialize SkillVersionManager.
        
        Args:
            skill_library: Dictionary mapping skill IDs to Skill objects
        """
        self.skill_library = skill_library
        # In a real implementation, this would likely load from a persistent history file
        self.version_history: Dict[str, List[Dict[str, Any]]] = {}
        
    def check_compatibility(self, skill_id: str, required_version_constraint: str) -> CompatibilityResult:
        """
        Check if the current version of a skill is compatible with a requirement.
        
        Args:
            skill_id: ID of the skill to check
            required_version_constraint: Version constraint (e.g., ">=1.0.0", "^2.0")
            
        Returns:
            CompatibilityResult object
        """
        skill = self.skill_library.get(skill_id)
        if not skill:
            return CompatibilityResult(
                compatible=False, 
                reason=f"Skill '{skill_id}' not found in library",
                issues=[f"Missing skill: {skill_id}"]
            )
            
        current_version = skill.version
        
        # Simple semantic version constraint parsing (basic implementation)
        # In a production system, use a library like 'packaging' or 'semver'
        is_compatible, reason = self._eval_constraint(current_version, required_version_constraint)
        
        issues = []
        if not is_compatible:
            issues.append(reason)
            
        if skill.deprecated:
            issues.append(f"Skill '{skill_id}' is deprecated.")
            if skill.replacement_skill_id:
                issues.append(f"Recommended replacement: {skill.replacement_skill_id}")
                
        return CompatibilityResult(
            compatible=is_compatible and not skill.deprecated,
            reason=None if is_compatible else reason,
            issues=issues,
            suggested_actions=["Upgrade skill library"] if not is_compatible else []
        )
        
    def resolve_dependencies(self, skill_ids: List[str]) -> Dict[str, str]:
        """
        Resolve all dependencies for a set of skills.
        
        Args:
            skill_ids: Initial list of skill IDs
            
        Returns:
            Dictionary mapping skill IDs to resolved versions
        """
        resolved: Dict[str, str] = {}
        to_resolve = list(skill_ids)
        visited = set()
        
        while to_resolve:
            current_id = to_resolve.pop(0)
            if current_id in visited:
                continue
                
            skill = self.skill_library.get(current_id)
            if not skill:
                # We can't resolve dependencies for a missing skill, 
                # but we'll include it in the resolved list if it was explicitly requested
                if current_id in skill_ids:
                    resolved[current_id] = "unknown"
                continue
                
            resolved[current_id] = skill.version
            visited.add(current_id)
            
            # Add dependencies to to_resolve list
            for dep in skill.dependencies:
                if dep.skill_id not in visited:
                    to_resolve.append(dep.skill_id)
                    
        return resolved
        
    def upgrade_skill(self, skill_id: str, target_version: str) -> UpgradeResult:
        """
        Simulate/Plan a skill upgrade.
        
        Args:
            skill_id: Skill ID to upgrade
            target_version: Target version string
            
        Returns:
            UpgradeResult object
        """
        skill = self.skill_library.get(skill_id)
        if not skill:
            return UpgradeResult(success=False, from_version="", to_version=target_version, error="Skill not found")
            
        current_version = skill.version
        
        # Check if target version is higher
        if not self._is_version_higher(target_version, current_version):
            return UpgradeResult(
                success=False, 
                from_version=current_version, 
                to_version=target_version, 
                error="Target version is not newer than current version"
            )
            
        # Detect breaking changes (major version increase)
        breaking = self._is_breaking_change(current_version, target_version)
        
        return UpgradeResult(
            success=True,
            from_version=current_version,
            to_version=target_version,
            changelog=skill.changelog,
            breaking_changes=breaking
        )
        
    def get_changelog(self, skill_id: str, from_version: Optional[str] = None) -> List[str]:
        """
        Get changelog for a skill.
        
        Args:
            skill_id: Skill ID
            from_version: Optional starting version
            
        Returns:
            List of changelog entries
        """
        skill = self.skill_library.get(skill_id)
        if not skill:
            return []
            
        if not from_version:
            return skill.changelog
            
        # In a real implementation, we would filter history
        return skill.changelog
        
    def _eval_constraint(self, version: str, constraint: str) -> Tuple[bool, str]:
        """Simple constraint evaluator"""
        if not constraint or constraint == "*" or constraint == "latest":
            return True, ""
            
        v_parts = [int(p) for p in version.split('.')]
        
        if constraint.startswith(">="):
            c_version = constraint[2:]
            c_parts = [int(p) for p in c_version.split('.')]
            if v_parts >= c_parts:
                return True, ""
            return False, f"Version {version} is less than required {constraint}"
            
        if constraint.startswith("^"): # Caret: compatible with major
            c_version = constraint[1:]
            c_parts = [int(p) for p in c_version.split('.')]
            if v_parts[0] == c_parts[0] and v_parts >= c_parts:
                return True, ""
            return False, f"Version {version} is not compatible with {constraint}"
            
        # Default equality check
        if version == constraint:
            return True, ""
            
        return False, f"Version {version} does not match {constraint}"
        
    def _is_version_higher(self, v1: str, v2: str) -> bool:
        """Check if v1 is strictly higher than v2"""
        try:
            parts1 = [int(p) for p in v1.split('.')]
            parts2 = [int(p) for p in v2.split('.')]
            return parts1 > parts2
        except (ValueError, AttributeError):
            return False
            
    def _is_breaking_change(self, old_v: str, new_v: str) -> bool:
        """Check if change from old_v to new_v is breaking (major version bump)"""
        try:
            old_major = int(old_v.split('.')[0])
            new_major = int(new_v.split('.')[0])
            return new_major > old_major
        except (ValueError, IndexError):
            return False
