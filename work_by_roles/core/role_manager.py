"""
Role manager for managing role definitions and validation.
Following Single Responsibility Principle - handles role management only.
"""

import json
import yaml
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    warnings.warn("jsonschema not available. Schema validation will be skipped.")

from .exceptions import ValidationError
from .models import (
    Skill, SkillRequirement, SkillBundle, SkillWorkflow,
    SkillStep, ConditionalBranch, LoopConfig, SkillStepConfig,
    SkillWorkflowTrigger, SkillWorkflowConfig, Role
)
from .variable_resolver import VariableResolver
from .models import ProjectContext


class RoleManager:
    """Manages role definitions and validation"""
    
    def __init__(self):
        self.roles: Dict[str, Role] = {}
        self.skill_library: Optional[Dict[str, Skill]] = None
        self.skill_bundles: Dict[str, SkillBundle] = {}
        self.skill_workflows: Dict[str, SkillWorkflow] = {}  # NEW: Skill workflow definitions
        self.role_hierarchy: Dict[str, Set[str]] = {}
        self.context: Optional[ProjectContext] = None
    
    def set_context(self, context: ProjectContext) -> None:
        """Set project context for variable resolution"""
        self.context = context

    def _validate_json_schema(self, schema: Dict[str, Any], schema_name: str) -> None:
        """Validate that a dict is a valid JSON Schema"""
        if not JSONSCHEMA_AVAILABLE:
            return  # Skip validation if jsonschema not available
        
        try:
            jsonschema.Draft7Validator.check_schema(schema)
        except jsonschema.SchemaError as e:
            raise ValidationError(
                f"Invalid JSON Schema in {schema_name}: {str(e)}",
                field=schema_name,
                context={"schema": schema}
            )

    def _resolve_schema_variables(self, schema: Any, context: Optional[ProjectContext]) -> Any:
        """Recursively resolve variables in a schema structure"""
        if isinstance(schema, dict):
            return {k: self._resolve_schema_variables(v, context) for k, v in schema.items()}
        elif isinstance(schema, list):
            return [self._resolve_schema_variables(item, context) for item in schema]
        elif isinstance(schema, str):
            return VariableResolver.resolve(schema, context)
        else:
            return schema

    def _parse_external_skill(self, data: Dict[str, Any]) -> Skill:
        """
        Adapt a standard (e.g. Anthropic/Tool) format skill to our internal Skill format.
        
        Expected standard format:
        {
            "name": "skill_name",
            "description": "skill description",
            "input_schema": { ... }
        }
        """
        skill_id = data.get("name", "").lower().replace(" ", "_")
        if not skill_id:
            raise ValidationError("External skill missing 'name' field")
            
        return Skill(
            id=skill_id,
            name=data.get("name", ""),
            description=VariableResolver.resolve(data.get("description", ""), self.context),
            dimensions=data.get("dimensions", ["external"]),
            levels=data.get("levels", {1: "Standard execution"}),
            tools=data.get("tools", []),
            constraints=data.get("constraints", []),
            input_schema=data.get("input_schema"),
            output_schema=data.get("output_schema"),
            error_handling=data.get("error_handling"),
            metadata=data.get("metadata", {"external": True})
        )

    def load_skill_library(self, schema_data: Dict[str, Any]) -> None:
        """Load skill library definitions"""
        if 'schema_version' not in schema_data:
            raise ValidationError("Missing schema_version in skill library")
        if 'skills' not in schema_data:
            raise ValidationError("Missing 'skills' in skill library")

        library: Dict[str, Skill] = {}
        for skill_data in schema_data.get('skills', []):
            required_fields = ['id', 'name', 'description']
            for field in required_fields:
                if field not in skill_data:
                    raise ValidationError(f"Missing required field '{field}' in skill definition")
            
            # category is optional, defaults to 'general'
            if 'category' not in skill_data:
                skill_data['category'] = 'general'

            skill_id = skill_data['id']
            if skill_id in library:
                raise ValidationError(f"Duplicate skill id '{skill_id}' in skill library")

            # Resolve variables in description and constraints
            description = VariableResolver.resolve(skill_data['description'], self.context)
            constraints = [VariableResolver.resolve(c, self.context) for c in skill_data.get('constraints', [])]
            tools = [VariableResolver.resolve(t, self.context) for t in skill_data.get('tools', [])]

            # Parse and validate new schema fields
            input_schema = None
            if 'input_schema' in skill_data:
                input_schema = self._resolve_schema_variables(skill_data['input_schema'], self.context)
                if isinstance(input_schema, dict):
                    self._validate_json_schema(input_schema, f"{skill_id}.input_schema")
            
            output_schema = None
            if 'output_schema' in skill_data:
                output_schema = self._resolve_schema_variables(skill_data['output_schema'], self.context)
                if isinstance(output_schema, dict):
                    self._validate_json_schema(output_schema, f"{skill_id}.output_schema")
            
            error_handling = None
            if 'error_handling' in skill_data:
                error_handling = self._resolve_schema_variables(skill_data['error_handling'], self.context)
                # Validate error_handling structure
                if isinstance(error_handling, dict):
                    if 'retry_strategy' in error_handling:
                        valid_strategies = ['exponential_backoff', 'linear_backoff', 'fixed_delay']
                        if error_handling['retry_strategy'] not in valid_strategies:
                            raise ValidationError(
                                f"Invalid retry_strategy in {skill_id}.error_handling. "
                                f"Must be one of: {valid_strategies}",
                                field=f"{skill_id}.error_handling.retry_strategy"
                            )
            
            metadata = None
            if 'metadata' in skill_data:
                metadata = skill_data['metadata']

            skill = Skill(
                id=skill_id,
                name=skill_data['name'],
                description=description,
                category=skill_data.get('category', 'general'),
                dimensions=skill_data.get('dimensions', []),
                levels=skill_data.get('levels', {}),
                tools=tools,
                constraints=constraints,
                input_schema=input_schema,
                output_schema=output_schema,
                error_handling=error_handling,
                metadata=metadata,
            )
            library[skill_id] = skill

        self.skill_library = library

        # Load external skills if present
        if 'external_skills' in schema_data:
            for ext_path in schema_data['external_skills']:
                try:
                    # Resolve path
                    path = Path(ext_path)
                    if self.context and not path.is_absolute():
                        path = self.context.root_path / path
                    
                    if not path.exists():
                        warnings.warn(f"External skill file not found: {path}")
                        continue
                        
                    with open(path, "r", encoding="utf-8") as f:
                        if path.suffix == ".json":
                            ext_data = json.load(f)
                        else:
                            ext_data = yaml.safe_load(f)
                    
                    if isinstance(ext_data, list):
                        for item in ext_data:
                            ext_skill = self._parse_external_skill(item)
                            if ext_skill.id in library:
                                warnings.warn(f"External skill '{ext_skill.id}' shadowed by library skill")
                            else:
                                library[ext_skill.id] = ext_skill
                    else:
                        ext_skill = self._parse_external_skill(ext_data)
                        if ext_skill.id in library:
                            warnings.warn(f"External skill '{ext_skill.id}' shadowed by library skill")
                        else:
                            library[ext_skill.id] = ext_skill
                except Exception as e:
                    warnings.warn(f"Failed to load external skill from {ext_path}: {e}")

        # Load skill bundles if present
        if 'skill_bundles' in schema_data:
            for bundle_data in schema_data['skill_bundles']:
                if 'id' not in bundle_data or 'skills' not in bundle_data:
                    raise ValidationError("Missing required fields in skill bundle definition")
                
                bundle_skills = []
                for s_req in bundle_data['skills']:
                    bundle_skills.append(self._parse_skill_requirement(s_req))
                
                bundle = SkillBundle(
                    id=bundle_data['id'],
                    name=bundle_data.get('name', bundle_data['id']),
                    description=VariableResolver.resolve(bundle_data.get('description', ""), self.context),
                    skills=bundle_skills
                )
                self.skill_bundles[bundle.id] = bundle
        
        # Load skill workflows if present (NEW)
        if 'skill_workflows' in schema_data:
            for workflow_data in schema_data['skill_workflows']:
                workflow = self._parse_skill_workflow(workflow_data)
                
                # Validate workflow against skill library
                errors = workflow.validate(library)
                if errors:
                    raise ValidationError(
                        f"Invalid skill workflow '{workflow.id}':\n" + 
                        "\n".join(f"  - {e}" for e in errors)
                    )
                
                self.skill_workflows[workflow.id] = workflow
    
    def _parse_skill_workflow(self, workflow_data: Dict[str, Any]) -> SkillWorkflow:
        """Parse a skill workflow from YAML data"""
        if 'id' not in workflow_data:
            raise ValidationError("Missing 'id' in skill workflow definition")
        if 'steps' not in workflow_data:
            raise ValidationError(f"Missing 'steps' in skill workflow '{workflow_data.get('id')}'")
        
        # Parse trigger
        trigger = SkillWorkflowTrigger()
        if 'trigger' in workflow_data:
            t_data = workflow_data['trigger']
            trigger = SkillWorkflowTrigger(
                stage_id=t_data.get('stage_id'),
                condition=t_data.get('condition', 'manual'),
                event_type=t_data.get('event_type')
            )
        
        # Parse config
        config = SkillWorkflowConfig()
        if 'config' in workflow_data:
            c_data = workflow_data['config']
            config = SkillWorkflowConfig(
                max_parallel=c_data.get('max_parallel', 2),
                fail_fast=c_data.get('fail_fast', False),
                retry_failed_steps=c_data.get('retry_failed_steps', True),
                timeout=c_data.get('timeout', 3600)
            )
        
        # Parse steps
        steps = []
        for step_data in workflow_data['steps']:
            step = self._parse_skill_step(step_data)
            steps.append(step)
        
        # Parse outputs
        outputs = workflow_data.get('outputs', {})
        
        return SkillWorkflow(
            id=workflow_data['id'],
            name=workflow_data.get('name', workflow_data['id']),
            description=VariableResolver.resolve(
                workflow_data.get('description', ''), 
                self.context
            ),
            steps=steps,
            trigger=trigger,
            outputs=outputs,
            config=config
        )
    
    def _parse_skill_step(self, step_data: Dict[str, Any]) -> SkillStep:
        """Parse a skill step from YAML data"""
        if 'step_id' not in step_data:
            raise ValidationError("Missing 'step_id' in skill step definition")
        
        # Check if dynamic skill selection is used
        dynamic_skill = step_data.get('dynamic_skill', False)
        if not dynamic_skill and 'skill_id' not in step_data:
            raise ValidationError(f"Missing 'skill_id' in skill step '{step_data.get('step_id')}'")
        
        # Parse step config
        step_config = SkillStepConfig()
        if 'config' in step_data:
            c_data = step_data['config']
            step_config = SkillStepConfig(
                timeout=c_data.get('timeout', 300),
                retry_on_failure=c_data.get('retry_on_failure', True),
                max_retries=c_data.get('max_retries', 3),
                required=c_data.get('required', False),
                parallel_with=c_data.get('parallel_with', [])
            )
        
        # Parse condition
        condition = step_data.get('condition')
        
        # Parse branches
        branches = []
        if 'branches' in step_data:
            for branch_data in step_data['branches']:
                branch = ConditionalBranch(
                    condition=branch_data.get('condition', ''),
                    target_step_id=branch_data.get('target_step_id', ''),
                    else_step_id=branch_data.get('else_step_id')
                )
                branches.append(branch)
        
        # Parse loop config
        loop_config = None
        if 'loop' in step_data:
            loop_data = step_data['loop']
            loop_config = LoopConfig(
                type=loop_data.get('type', 'while'),
                condition=loop_data.get('condition'),
                items_source=loop_data.get('items_source'),
                max_iterations=loop_data.get('max_iterations', 100),
                break_on_failure=loop_data.get('break_on_failure', False)
            )
        
        # Parse dynamic skill selection config
        skill_selector_config = None
        fallback_skill_id = None
        if dynamic_skill:
            skill_selector_config = step_data.get('skill_selector', {})
            fallback_skill_id = step_data.get('fallback_skill_id')
        
        return SkillStep(
            step_id=step_data['step_id'],
            skill_id=step_data.get('skill_id', ''),  # May be empty for dynamic skills
            name=step_data.get('name', step_data['step_id']),
            order=step_data.get('order', 1),
            depends_on=step_data.get('depends_on', []),
            inputs=step_data.get('inputs', {}),
            outputs=step_data.get('outputs', []),
            config=step_config,
            condition=condition,
            branches=branches,
            loop_config=loop_config,
            dynamic_skill=dynamic_skill,
            skill_selector_config=skill_selector_config,
            fallback_skill_id=fallback_skill_id
        )
    
    def get_workflow(self, workflow_id: str) -> Optional[SkillWorkflow]:
        """Get a skill workflow by ID"""
        return self.skill_workflows.get(workflow_id)
    
    def get_workflows_for_stage(self, stage_id: str) -> List[SkillWorkflow]:
        """Get all workflows that trigger on a specific stage"""
        return [
            wf for wf in self.skill_workflows.values()
            if wf.trigger.stage_id == stage_id and wf.trigger.condition == 'auto'
        ]
    
    def load_roles(self, schema_data: Dict[str, Any]) -> None:
        """Load roles from schema"""
        if 'schema_version' not in schema_data:
            raise ValidationError("Missing schema_version in role schema")
        
        if 'roles' not in schema_data:
            raise ValidationError("Missing 'roles' in schema")
        
        for role_data in schema_data['roles']:
            role = self._parse_role(role_data)
            self.roles[role.id] = role
            self._build_hierarchy(role)
    
    def _parse_role(self, role_data: Dict[str, Any]) -> Role:
        """Parse role from schema data"""
        required_fields = ['id', 'name', 'description', 'skills', 'domain', 'responsibility']
        for field in required_fields:
            if field not in role_data:
                raise ValidationError(f"Missing required field '{field}' in role definition")
        
        # 解析技能列表（新格式：直接引用技能ID）
        skills: List[str] = []
        if 'skills' in role_data:
            if isinstance(role_data['skills'], list):
                skills = role_data['skills']
            else:
                raise ValidationError(f"Field 'skills' must be a list of skill IDs")
        
        # 验证技能是否存在
        if skills and self.skill_library is not None:
            for skill_id in skills:
                if skill_id not in self.skill_library:
                    raise ValidationError(
                        f"Skill '{skill_id}' referenced by role '{role_data['id']}' not found in skill library",
                        field="skills",
                        value=skill_id,
                        context={"role_id": role_data['id']}
                    )
        
        # 解析领域和职责
        domain = role_data.get('domain', '')
        responsibility = role_data.get('responsibility', '')
        
        # Resolve variables in description and validation rules
        description = VariableResolver.resolve(role_data['description'], self.context)
        validation_rules = [
            VariableResolver.resolve(r, self.context) 
            for r in role_data.get('validation_rules', [])
        ]
        
        # 解析约束（可选）
        constraints = role_data.get('constraints', {})
        if not isinstance(constraints, dict):
            constraints = {}

        return Role(
            id=role_data['id'],
            name=role_data['name'],
            description=description,
            skills=skills,
            domain=domain,
            responsibility=responsibility,
            extends=role_data.get('extends'),
            constraints=constraints,
            validation_rules=validation_rules,
            instruction_template=role_data.get('instruction_template', "")
        )

    def _resolve_skill_requirements(self, requirements: List[SkillRequirement], role_id: str) -> List[SkillRequirement]:
        """Resolve skill bundles and validate skills exist"""
        resolved: Dict[str, SkillRequirement] = {}
        
        to_process = list(requirements)
        while to_process:
            req = to_process.pop(0)
            
            # Check if it's a bundle
            if req.skill_id in self.skill_bundles:
                bundle = self.skill_bundles[req.skill_id]
                to_process.extend(bundle.skills)
                continue
            
            # It's a regular skill
            # Validate skill exists if library is loaded (even if empty)
            if self.skill_library is not None and req.skill_id not in self.skill_library:
                raise ValidationError(
                    f"Skill '{req.skill_id}' referenced by role '{role_id}' not found in skill library",
                    field="required_skills",
                    value=req.skill_id,
                    context={"role_id": role_id}
                )
            
            # Merge requirements (keep highest min_level)
            if req.skill_id in resolved:
                existing = resolved[req.skill_id]
                resolved[req.skill_id] = SkillRequirement(
                    skill_id=req.skill_id,
                    min_level=max(existing.min_level, req.min_level),
                    focus=list(set((existing.focus or []) + (req.focus or []))) or None
                )
            else:
                resolved[req.skill_id] = req
                
        return list(resolved.values())

    def _parse_skill_requirement(self, requirement_data: Dict[str, Any]) -> SkillRequirement:
        """Parse skill requirement"""
        if 'skill_id' not in requirement_data:
            raise ValidationError("Missing 'skill_id' in required_skills entry")
        return SkillRequirement(
            skill_id=requirement_data['skill_id'],
            min_level=int(requirement_data.get('min_level', 1)),
            focus=requirement_data.get('focus')
        )
    
    def _build_hierarchy(self, role: Role) -> None:
        """Build role hierarchy"""
        if role.id not in self.role_hierarchy:
            self.role_hierarchy[role.id] = set()
        
        if role.extends:
            for parent_id in role.extends:
                if parent_id not in self.roles:
                    raise ValidationError(
                        f"Parent role '{parent_id}' not found for role '{role.id}'",
                        field="extends",
                        value=parent_id,
                        context={"role_id": role.id, "parent_id": parent_id}
                    )
                self.role_hierarchy[role.id].add(parent_id)
                # Inherit parent's hierarchy
                if parent_id in self.role_hierarchy:
                    self.role_hierarchy[role.id].update(self.role_hierarchy[parent_id])
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """Get role by ID"""
        return self.roles.get(role_id)
    
    def validate_role_exists(self, role_id: str) -> bool:
        """Validate that role exists"""
        return role_id in self.roles
    
    def validate_action(self, role_id: str, action: str) -> bool:
        """Validate if action is allowed for role"""
        if role_id not in self.roles:
            return False
        
        role = self.roles[role_id]
        allowed = role.constraints.get('allowed_actions', [])
        forbidden = role.constraints.get('forbidden_actions', [])
        
        # Check direct role
        if action in forbidden:
            return False
        if action in allowed:
            return True
        
        # Check inherited roles
        inherited_roles = self.role_hierarchy.get(role_id, set())
        for parent_id in inherited_roles:
            parent_role = self.roles.get(parent_id)
            if parent_role:
                if action in parent_role.constraints.get('forbidden_actions', []):
                    return False
                if action in parent_role.constraints.get('allowed_actions', []):
                    return True
        
        return False

