"""
Configuration loader with dependency management.
Following Single Responsibility Principle - handles configuration loading only.
"""

import re
import warnings
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, cast

from .exceptions import ValidationError
from .models import ProjectContext
from .schema_loader import SchemaLoader


class ConfigLoader:
    """Unified configuration loader with dependency management"""
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)
        self._cache: Dict[Path, Tuple[Any, float]] = {}

    def _load_skill_directory(self, skill_dir: Path) -> Dict[str, Any]:
        """
        Load skills from a directory in Anthropic standard format.
        
        Expected structure:
        skills/
          <skill_name>/
            Skill.md          # Anthropic standard (YAML frontmatter + Markdown)
            resources/        # Optional resources
        """
        if not skill_dir.exists():
            raise ValidationError(f"Skill directory not found: {skill_dir}")
        
        # Support both flat structure and nested structure
        skills_root = skill_dir
        if (skill_dir / "skills").exists():
            skills_root = skill_dir / "skills"
        
        skills: List[Dict[str, Any]] = []
        for entry in sorted(skills_root.iterdir()):
            if not entry.is_dir():
                continue
            
            skill_md = entry / "Skill.md"
            if not skill_md.exists():
                continue
            
            try:
                skill_data = self._load_anthropic_skill(skill_md, entry)
                if skill_data:
                    skills.append(skill_data)
            except Exception as e:
                warnings.warn(f"Failed to load skill from {skill_md}: {e}")
                continue
        
        if not skills:
            raise ValidationError(f"No skills found in {skills_root}")
        
        return {
            "schema_version": "1.0",
            "skills": skills
        }
    
    def _load_anthropic_skill(self, skill_md_path: Path, skill_dir: Path) -> Dict[str, Any]:
        """
        Load skill from Anthropic standard Skill.md format.
        
        Format: YAML frontmatter (---) + Markdown content
        """
        import yaml
        
        content = skill_md_path.read_text(encoding='utf-8')
        
        # Parse YAML frontmatter
        frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(frontmatter_pattern, content, re.DOTALL)
        
        if not match:
            raise ValidationError(
                f"Invalid Skill.md format: {skill_md_path}. "
                f"Expected YAML frontmatter between --- markers."
            )
        
        yaml_content = match.group(1)
        markdown_content = match.group(2)
        
        # Parse YAML
        try:
            frontmatter_data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML in Skill.md frontmatter: {skill_md_path}: {e}")
        
        if not frontmatter_data:
            raise ValidationError(f"Empty frontmatter in Skill.md: {skill_md_path}")
        
        # Extract required fields
        skill_id = frontmatter_data.get('id') or skill_dir.name
        name = frontmatter_data.get('name', '')
        description = frontmatter_data.get('description', '')
        
        if not name:
            raise ValidationError(f"Missing 'name' in Skill.md frontmatter: {skill_md_path}")
        if not description:
            raise ValidationError(f"Missing 'description' in Skill.md frontmatter: {skill_md_path}")
        
        # Build skill data dict (compatible with existing parser)
        skill_data = {
            'id': skill_id,
            'name': name,
            'description': description,
            'category': frontmatter_data.get('category', 'general'),  # Default to 'general' if not specified
            'dimensions': frontmatter_data.get('dimensions', []),
            'levels': frontmatter_data.get('levels', {}),
            'tools': frontmatter_data.get('tools', []),
            'constraints': frontmatter_data.get('constraints', []),
            'input_schema': frontmatter_data.get('input_schema'),
            'output_schema': frontmatter_data.get('output_schema'),
            'error_handling': frontmatter_data.get('error_handling'),
            # Add manifest fields
            'skill_type': frontmatter_data.get('skill_type'),
            'side_effects': frontmatter_data.get('side_effects', []),
            'deterministic': frontmatter_data.get('deterministic', False),
            'testable': frontmatter_data.get('testable', True),
            'metadata': {
                'anthropic_format': True,
                'markdown_content': markdown_content,
                'skill_dir': str(skill_dir),
                **frontmatter_data.get('metadata', {})
            }
        }
        
        return skill_data
    
    def load_all(
        self,
        skill_file: Path,
        roles_file: Path,
        workflow_file: Path,
        context_file: Optional[Path] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Optional[ProjectContext]]:
        """
        Load all configurations in the correct order, handling dependencies.
        
        Args:
            skill_file: Path to skill library file
            roles_file: Path to roles schema file
            workflow_file: Path to workflow schema file
            context_file: Optional path to project context file
            
        Returns:
            Tuple of (skill_data, roles_data, workflow_data, context)
            
        Raises:
            ValidationError: If any configuration is invalid or dependencies are missing
        """
        errors: List[str] = []
        context: Optional[ProjectContext] = None
        skill_data: Dict[str, Any] = {}
        roles_data: Dict[str, Any] = {}
        workflow_data: Dict[str, Any] = {}
        
        # Step 1: Load context first (if exists) - no dependencies
        if context_file and context_file.exists():
            try:
                context_data = self._load_cached(context_file)
                context = ProjectContext.from_dict(self.workspace_path, context_data)
            except Exception as e:
                errors.append(f"Failed to load context from {context_file}: {e}")
        
        # Step 2: Load skill library - no dependencies
        try:
            if skill_file.is_dir():
                skill_data = self._load_skill_directory(skill_file)
            else:
                raise ValidationError(
                    f"Skill library must be a directory with Skill.md files. "
                    f"Found file: {skill_file}. Please use directory structure."
                )
            if 'schema_version' not in skill_data:
                errors.append(f"Missing schema_version in skill library {skill_file}")
            if 'skills' not in skill_data:
                errors.append(f"Missing 'skills' in skill library {skill_file}")
        except Exception as e:
            errors.append(f"Failed to load skill library from {skill_file}: {e}")
        
        # Step 3: Load roles - depends on skill library
        try:
            roles_data = self._load_cached(roles_file)
            if 'schema_version' not in roles_data:
                errors.append(f"Missing schema_version in roles schema {roles_file}")
            if 'roles' not in roles_data:
                errors.append(f"Missing 'roles' in roles schema {roles_file}")
        except Exception as e:
            errors.append(f"Failed to load roles from {roles_file}: {e}")
        
        # Step 4: Load workflow - depends on roles
        try:
            workflow_data = self._load_cached(workflow_file)
            if 'schema_version' not in workflow_data:
                errors.append(f"Missing schema_version in workflow schema {workflow_file}")
            if 'workflow' not in workflow_data:
                errors.append(f"Missing 'workflow' in workflow schema {workflow_file}")
        except Exception as e:
            errors.append(f"Failed to load workflow from {workflow_file}: {e}")
        
        # If any critical errors occurred, raise them now
        if errors:
            error_msg = "Configuration loading errors:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValidationError(error_msg)
        
        return skill_data, roles_data, workflow_data, context
    
    def _load_cached(self, file_path: Path) -> Dict[str, Any]:
        """Load file with caching based on modification time"""
        try:
            mtime = file_path.stat().st_mtime
            if file_path in self._cache:
                cached_data, cached_mtime = self._cache[file_path]
                if mtime == cached_mtime:
                    return cast(Dict[str, Any], cached_data)
            
            data = SchemaLoader.load_schema(file_path)
            self._cache[file_path] = (data, mtime)
            return cast(Dict[str, Any], data)
        except FileNotFoundError:
            raise ValidationError(f"Configuration file not found: {file_path}")
        except Exception as e:
            raise ValidationError(f"Failed to load configuration from {file_path}: {e}")
    
    def validate_dependencies(
        self,
        skill_data: Dict[str, Any],
        roles_data: Dict[str, Any],
        workflow_data: Dict[str, Any]
    ) -> List[str]:
        """
        Validate dependencies between configurations.
        
        Returns:
            List of error messages (empty if all valid)
        """
        errors = []
        
        # Build skill library map
        skill_library = {}
        if skill_data and 'skills' in skill_data:
            for skill in skill_data['skills']:
                if 'id' in skill:
                    skill_library[skill['id']] = skill
        
        # Validate role skill references
        if roles_data and 'roles' in roles_data:
            for role in roles_data['roles']:
                role_id = role.get('id', 'unknown')
                
                # Check skills (new format: direct skill ID list)
                if 'skills' in role:
                    for skill_id in role['skills']:
                        if skill_id and skill_id not in skill_library:
                            errors.append(
                                f"Role '{role_id}' references skill '{skill_id}' "
                                f"which is not found in skill library"
                            )
                
                # Backward compatibility: check 'skills' field
                elif 'skills' in role:
                    for skill_id in role['skills']:
                        if skill_id not in skill_library:
                            errors.append(
                                f"Role '{role_id}' references skill '{skill_id}' "
                                f"which is not found in skill library"
                            )
        
        # Validate workflow role references
        if workflow_data and 'workflow' in workflow_data:
            workflow_info = workflow_data['workflow']
            workflow_id = workflow_info.get('id', 'unknown')
            
            # Build role map (we need roles_data to be loaded into RoleManager first)
            # This validation happens after roles are loaded into RoleManager
            # So we'll do a basic check here and full validation in RoleManager
            
            if 'stages' in workflow_info:
                for stage in workflow_info['stages']:
                    stage_id = stage.get('id', 'unknown')
                    role_id = stage.get('role')
                    if not role_id:
                        errors.append(f"Stage '{stage_id}' in workflow '{workflow_id}' missing 'role' field")
        
        return errors
    
    def clear_cache(self) -> None:
        """Clear the configuration cache"""
        self._cache.clear()

