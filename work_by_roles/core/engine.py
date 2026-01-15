"""
Multi-Role Skills Workflow Engine
Core Framework Implementation

This module is being refactored following SOLID principles.
Some classes have been moved to separate modules for better organization.
For backward compatibility, all classes are still exported from here.
"""

import json
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Callable, Tuple, cast
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from datetime import datetime
import time
import warnings
from difflib import SequenceMatcher
from collections import Counter

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    warnings.warn("jsonschema not available. Schema validation will be skipped.")

# Import from refactored modules
from .exceptions import ValidationError, WorkflowError, SecurityError
from .enums import StageStatus, SkillErrorType, SkillWorkflowStepStatus
from .models import (
    Skill, SkillExecution, SkillRequirement, SkillBundle,
    ConditionalBranch, LoopConfig, SkillStepConfig, SkillStep,
    SkillWorkflowTrigger, SkillWorkflowConfig, SkillWorkflow,
    SkillWorkflowExecution, Role, QualityGate, Output, Stage,
    Workflow, ExecutionState, ProjectContext, AgentContext,
    ContextSummary
)
from .execution_tracker import ExecutionTracker
from .skill_selector import SkillSelector, RetryHandler
from .condition_evaluator import ConditionEvaluator
from .variable_resolver import VariableResolver
from .project_scanner import ProjectScanner
from .schema_loader import SchemaLoader, normalize_path
from .config_loader import ConfigLoader
from .role_manager import RoleManager
from .workflow_executor import WorkflowExecutor
from .state_storage import StateStorage, FileStateStorage
from .team_manager import TeamManager
from .quality_gates import QualityGateSystem

# Re-export for backward compatibility
__all__ = [
    'ValidationError', 'WorkflowError', 'SecurityError',
    'StageStatus', 'SkillErrorType', 'SkillWorkflowStepStatus',
    'Skill', 'SkillExecution', 'SkillRequirement', 'SkillBundle',
    'ConditionalBranch', 'LoopConfig', 'SkillStepConfig', 'SkillStep',
    'SkillWorkflowTrigger', 'SkillWorkflowConfig', 'SkillWorkflow',
    'SkillWorkflowExecution', 'Role', 'QualityGate', 'Output', 'Stage',
    'Workflow', 'ExecutionState', 'ProjectContext', 'AgentContext',
    'ContextSummary', 'ExecutionTracker', 'SkillSelector', 'RetryHandler',
    'ConditionEvaluator', 'VariableResolver',
]

# ============================================================================
# Remaining classes that haven't been moved yet
# These will be gradually moved to separate modules
# ============================================================================

# Note: The following classes have been moved to separate modules:
# - ValidationError, WorkflowError, SecurityError -> exceptions.py
# - StageStatus, SkillErrorType, SkillWorkflowStepStatus -> enums.py
# - Skill, SkillExecution, SkillRequirement, SkillBundle -> models.py
# - ConditionalBranch, LoopConfig, SkillStepConfig, SkillStep -> models.py
# - SkillWorkflowTrigger, SkillWorkflowConfig, SkillWorkflow -> models.py
# - SkillWorkflowExecution, Role, QualityGate, Output, Stage -> models.py
# - Workflow, ExecutionState, ProjectContext, AgentContext, ContextSummary -> models.py
# - ExecutionTracker -> execution_tracker.py
# - SkillSelector, RetryHandler -> skill_selector.py
# - ConditionEvaluator -> condition_evaluator.py
# - VariableResolver -> variable_resolver.py
#
# They are imported above and re-exported for backward compatibility.
# The original class definitions below have been removed to avoid duplication.

# Remaining classes that still need to be moved:
# - ProjectScanner
# - SchemaLoader
# - ConfigLoader
# - RoleManager
# - WorkflowExecutor
# - StateStorage, FileStateStorage
# - TeamManager
# - QualityGateSystem
# - WorkflowEngine
# - IntentRouter
# - Agent
# - SkillInvoker, PlaceholderSkillInvoker, LLMSkillInvoker, CompositeSkillInvoker
# - SkillWorkflowExecutor
# - AgentOrchestrator
# - RoleExecutor
# - SkillBenchmark

# Note: The following duplicate class definitions have been removed.
# They are now imported from the refactored modules above.
# If you see any class definitions below that match the moved classes,
# they should be removed to avoid conflicts.


# All the above classes have been moved to separate modules:
# - SkillExecution, SkillRequirement, SkillBundle -> models.py
# - SkillWorkflowStepStatus -> enums.py
# - ConditionalBranch, LoopConfig, SkillStepConfig, SkillStep -> models.py
# - SkillWorkflowTrigger, SkillWorkflowConfig, SkillWorkflow -> models.py
# - SkillWorkflowExecution, Role, QualityGate, Output, Stage -> models.py
# - Workflow, ExecutionState, ProjectContext -> models.py
# - ProjectScanner -> project_scanner.py
# - SchemaLoader, normalize_path -> schema_loader.py
# - ConfigLoader -> config_loader.py
# They are imported above and re-exported for backward compatibility.

# Remaining classes that still need to be moved:
# - SecurityError (already in exceptions.py, but duplicate here)
# - RoleManager (501 lines)
# - WorkflowExecutor (135 lines)
# - StateStorage, FileStateStorage (56 lines total)
# - TeamManager (235 lines)
# - QualityGateSystem (186 lines)
# - WorkflowEngine (921 lines - needs splitting)
# - IntentRouter (632 lines - needs splitting)
# - Agent (156 lines)
# - SkillInvoker series (403 lines total)
# - SkillWorkflowExecutor (563 lines - needs splitting)
# - AgentOrchestrator (525 lines - needs splitting)
# - RoleExecutor (303 lines)
# - SkillBenchmark (163 lines)


class SecurityError(Exception):
    """Scans project structure to build ProjectContext"""
    
    def __init__(self, root_path: Path):
        self.root_path = root_path

    def scan(self) -> ProjectContext:
        ctx = ProjectContext(root_path=self.root_path)
        
        # 1. Scan Paths - more comprehensive scanning
        path_patterns = {
            "src": ["src", "app", "lib", "core", "work_by_roles", "workflow_engine"],
            "tests": ["tests", "test", "spec", "__tests__"],
            "docs": ["docs", "doc", "documentation"],
            "config": [".workflow", "config", "settings"]
        }
        
        for key, patterns in path_patterns.items():
            for p in patterns:
                dir_path = self.root_path / p
                if dir_path.is_dir():
                    ctx.paths[key] = p
                    break
        
        # If no src found, try to find Python package directories
        if "src" not in ctx.paths:
            excluded_names = {ctx.paths.get("tests"), ctx.paths.get("docs"), ctx.paths.get("config")}
            excluded_names.discard(None)  # Remove None values
            
            for item in self.root_path.iterdir():
                if item.is_dir() and not item.name.startswith('.') and not item.name.startswith('__'):
                    # Check if it looks like a Python package (has __init__.py)
                    init_file = item / "__init__.py"
                    if init_file.exists():
                        # Check if it's not already categorized
                        if item.name not in excluded_names:
                            ctx.paths["src"] = item.name
                            break
        
        # 2. Scan Specs - more comprehensive patterns
        spec_patterns = [
            "*.spec.md", "*.spec.yaml", "*.spec.yml",
            "openapi.yaml", "openapi.yml", "openapi.json",
            "swagger.yaml", "swagger.yml", "swagger.json",
            "schema.json", "schema.yaml", "schema.yml",
            "api.yaml", "api.yml", "api.json",
            "*.api.md", "*.api.yaml"
        ]
        for p in spec_patterns:
            for match in self.root_path.glob(f"**/{p}"):
                if ".workflow" in str(match) or ".git" in str(match):
                    continue
                rel_path = match.relative_to(self.root_path)
                name = match.stem.replace(".spec", "").replace(".api", "")
                if name:
                    ctx.specs[name] = str(rel_path)

        # 3. Scan Standards - more comprehensive file detection
        standards_files = {
            "ruff": ["ruff.toml", ".ruff.toml", "ruff.yaml", ".ruff.yaml"],
            "mypy": ["mypy.ini", ".mypy.ini", "mypy.ini", "pyproject.toml"],
            "pytest": ["pytest.ini", "pyproject.toml", "setup.cfg", ".pytest.ini"],
            "black": ["pyproject.toml", ".black", "black.toml"],
            "flake8": [".flake8", "setup.cfg", "tox.ini"],
            "eslint": [".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml", "package.json"],
            "prettier": [".prettierrc", ".prettierrc.json", ".prettierrc.yaml", "package.json"],
            "typescript": ["tsconfig.json", "tsconfig.base.json"],
            "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile", "poetry.lock"],
            "node": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
            "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"],
            "git": [".gitignore", ".gitattributes"],
            "ci": [".github/workflows", ".gitlab-ci.yml", ".travis.yml", "Jenkinsfile", ".circleci"]
        }
        
        for tool, files in standards_files.items():
            for f in files:
                file_path = self.root_path / f
                # Handle directory-based configs (like .github/workflows)
                if file_path.is_dir() and file_path.exists():
                    ctx.standards[tool] = f
                    break
                elif file_path.is_file() and file_path.exists():
                    ctx.standards[tool] = f
                    break
        
        # 4. Additional project metadata scanning
        # Try to detect project type and add relevant info
        # If python standard wasn't detected but Python files exist, add it
        if "python" not in ctx.standards:
            if (self.root_path / "setup.py").exists():
                ctx.standards["python"] = "setup.py"
            elif (self.root_path / "requirements.txt").exists():
                ctx.standards["python"] = "requirements.txt"
            elif (self.root_path / "Pipfile").exists():
                ctx.standards["python"] = "Pipfile"
                    
        return ctx


# SecurityError and normalize_path have been moved to schema_loader.py
# They are imported above and re-exported for backward compatibility.


# Remaining classes that still need to be moved:
# - RoleManager (501 lines)
# - WorkflowExecutor (135 lines)
# - StateStorage, FileStateStorage (56 lines total)
# - TeamManager (235 lines)
# - QualityGateSystem (186 lines)
# - WorkflowEngine (921 lines - needs splitting)
# - IntentRouter (632 lines - needs splitting)
# - Agent (156 lines)
# - SkillInvoker series (403 lines total)
# - SkillWorkflowExecutor (563 lines - needs splitting)
# - AgentOrchestrator (525 lines - needs splitting)
# - RoleExecutor (303 lines)
# - SkillBenchmark (163 lines)


# SchemaLoader, ConfigLoader, and RoleManager have been moved to separate modules
# They are imported above and re-exported for backward compatibility.


# WorkflowExecutor, StateStorage, and FileStateStorage have been moved to separate modules
# They are imported above and re-exported for backward compatibility.

# Remaining classes that still need to be moved:
# - TeamManager (235 lines)
# - QualityGateSystem (186 lines)
# - WorkflowEngine (921 lines - needs splitting)
# - IntentRouter (632 lines - needs splitting)
# - Agent (156 lines)
# - SkillInvoker series (403 lines total)
# - SkillWorkflowExecutor (563 lines - needs splitting)
# - AgentOrchestrator (525 lines - needs splitting)
# - RoleExecutor (303 lines)
# - SkillBenchmark (163 lines)


# WorkflowExecutor, StateStorage, and FileStateStorage have been moved to separate modules
# They are imported above and re-exported for backward compatibility.


# WorkflowExecutor, StateStorage, and FileStateStorage have been moved to separate modules
# TeamManager and QualityGateSystem have been moved to separate modules
# TeamManager and QualityGateSystem have been moved to separate modules
# They are imported above and re-exported for backward compatibility.


class WorkflowEngine:
    """Main workflow engine"""
    
    def __init__(
        self,
        workspace_path: Path,
        role_manager: Optional[RoleManager] = None,
        quality_gates: Optional[QualityGateSystem] = None,
        state_storage: Optional[StateStorage] = None,
        auto_save_state: bool = True,
        state_file: Optional[Path] = None
    ):
        """
        Initialize workflow engine.
        
        Args:
            workspace_path: Path to workspace root
            role_manager: Optional RoleManager instance (for dependency injection)
            quality_gates: Optional QualityGateSystem instance (for dependency injection)
            state_storage: Optional StateStorage instance (for dependency injection)
            auto_save_state: Whether to automatically save state on stage transitions
            state_file: Path to state file (default: .workflow/state.yaml)
        """
        self.workspace_path = Path(workspace_path)
        self.role_manager = role_manager or RoleManager()
        self.workflow: Optional[Workflow] = None
        self.executor: Optional[WorkflowExecutor] = None
        self.quality_gates = quality_gates or QualityGateSystem(self.role_manager)
        self.context: Optional[ProjectContext] = None
        self.state_storage = state_storage or FileStateStorage()
        self.auto_save_state = auto_save_state
        self.state_file = state_file or (self.workspace_path / ".workflow" / "state.yaml")
    
    def load_context(self, context_file: Path) -> None:
        """Load project context from file"""
        if context_file.exists():
            data = SchemaLoader.load_schema(context_file)
            self.context = ProjectContext.from_dict(self.workspace_path, data)
            self.role_manager.set_context(self.context)

    def save_state(self, state_file: Optional[Path] = None) -> None:
        """
        Save execution state to file.
        
        Args:
            state_file: Optional path to state file (defaults to self.state_file)
        """
        if not self.executor:
            return
        
        target_file = state_file or self.state_file
        self.state_storage.save(self.executor.state, target_file)

    def load_state(self, state_file: Optional[Path] = None, auto_restore: bool = True) -> bool:
        """
        Load execution state from file.
        
        Args:
            state_file: Optional path to state file (defaults to self.state_file)
            auto_restore: Whether to automatically restore state if executor exists
            
        Returns:
            True if state was loaded, False otherwise
        """
        target_file = state_file or self.state_file
        
        if not auto_restore or not self.executor:
            return False
        
        state = self.state_storage.load(target_file)
        if state is not None:
            self.executor.state = state
            return True
        return False
    
    def _auto_save_state(self) -> None:
        """Internal method to automatically save state if enabled"""
        if self.auto_save_state and self.executor:
            try:
                self.save_state()
            except Exception:
                # Already handled gracefully in StateStorage.save()
                pass

    def load_all_configs(
        self,
        skill_file: Path,
        roles_file: Path,
        workflow_file: Path,
        context_file: Optional[Path] = None
    ) -> None:
        """
        Load all configurations in the correct order using ConfigLoader.
        This is the recommended method for loading configurations.
        
        Args:
            skill_file: Path to skill library file
            roles_file: Path to roles schema file
            workflow_file: Path to workflow schema file
            context_file: Optional path to project context file
        """
        config_loader = ConfigLoader(self.workspace_path)
        
        # Load all configs in correct order
        skill_data, roles_data, workflow_data, context = config_loader.load_all(
            skill_file, roles_file, workflow_file, context_file
        )
        
        # Set context first if available
        if context:
            self.context = context
            self.role_manager.set_context(context)
        
        # Load skill library
        self.role_manager.load_skill_library(skill_data)
        
        # Load roles (will validate skill references)
        self.role_manager.load_roles(roles_data)
        
        # Validate dependencies
        dep_errors = config_loader.validate_dependencies(skill_data, roles_data, workflow_data)
        if dep_errors:
            error_msg = "Configuration dependency errors:\n" + "\n".join(f"  - {e}" for e in dep_errors)
            raise ValidationError(error_msg)
        
        # Load workflow (workflow_data is already the full schema dict)
        self._load_workflow_from_data(workflow_data)

    def load_skill_library(self, skill_file: Path) -> None:
        """Load skill library definitions - Anthropic format only"""
        if not skill_file.exists():
            raise ValidationError(f"Skill file/directory not found: {skill_file}")
        
        # Only support directory structure with Skill.md files
        if skill_file.is_dir():
            loader = ConfigLoader(self.workspace_path)
            schema_data = loader._load_skill_directory(skill_file)
        else:
            raise ValidationError(
                f"Skills must be in directory format with Skill.md files. "
                f"Found file: {skill_file}. Please migrate to directory structure."
            )
        self.role_manager.load_skill_library(schema_data)
    
    def load_roles(self, roles_file: Path) -> None:
        """Load role definitions (backward compatible)"""
        schema_data = SchemaLoader.load_schema(roles_file)
        self.role_manager.load_roles(schema_data)
    
    def load_workflow(self, workflow_file: Path) -> None:
        """Load workflow definition (backward compatible)"""
        schema_data = SchemaLoader.load_schema(workflow_file)
        self._load_workflow_from_data(schema_data)
        
    def _load_workflow_from_data(self, schema_data: Dict[str, Any]) -> None:
        """Internal method to load workflow from schema data"""
        if 'schema_version' not in schema_data:
            raise ValidationError("Missing schema_version in workflow schema")
        
        if 'workflow' not in schema_data:
            raise ValidationError("Missing 'workflow' in schema")
        
        workflow_data = schema_data['workflow']
        stages = []
        
        for stage_data in workflow_data['stages']:
            quality_gates = [
                QualityGate(
                    type=gate_data['type'],
                    criteria=gate_data['criteria'],
                    validator=gate_data['validator'],
                    strict=gate_data.get('strict', False)  # Default to relaxed mode (vibe coding style)
                )
                for gate_data in stage_data.get('quality_gates', [])
            ]
            
            outputs = [
                Output(
                    type=out_data['type'],
                    format=out_data['format'],
                    required=out_data['required'],
                    name=out_data['name']
                )
                for out_data in stage_data.get('outputs', [])
            ]
            
            stage = Stage(
                id=stage_data['id'],
                name=stage_data['name'],
                role=stage_data['role'],
                order=stage_data['order'],
                prerequisites=stage_data.get('prerequisites', []),
                entry_criteria=stage_data.get('entry_criteria', []),
                exit_criteria=stage_data.get('exit_criteria', []),
                quality_gates=quality_gates,
                outputs=outputs,
                goal_template=stage_data.get('goal_template', "")
            )
            stages.append(stage)
        
        self.workflow = Workflow(
            id=workflow_data['id'],
            name=workflow_data['name'],
            description=workflow_data['description'],
            stages=stages
        )
        
        self.executor = WorkflowExecutor(self.workflow, self.role_manager)
        
        # Auto-restore state after workflow is loaded
        if self.auto_save_state:
            self.load_state(auto_restore=True)
            # Generate initial vibe context
            self.update_vibe_context()
    
    def start_stage(self, stage_id: str, role_id: str) -> None:
        """Start a workflow stage"""
        if not self.executor:
            raise WorkflowError("Workflow not loaded")
        self.executor.start_stage(stage_id, role_id)
        self._auto_save_state()
        # Update vibe context for AI awareness
        if self.auto_save_state:
            self.update_vibe_context()
    
    def complete_stage(self, stage_id: str) -> Tuple[bool, List[str]]:
        """Complete a stage after passing quality gates"""
        if not self.executor:
            raise WorkflowError("Workflow not loaded")
        
        stage = self.executor._get_stage_by_id(stage_id)
        if not stage:
            raise WorkflowError(f"Stage '{stage_id}' not found")
        
        # Evaluate all quality gates
        all_passed = True
        all_errors = []
        warnings_only = []  # Errors from non-strict gates
        
        for gate in stage.quality_gates:
            passed, errors = self.quality_gates.evaluate_gate(gate, stage, self.workspace_path)
            if not passed:
                if gate.strict:
                    # Strict mode: errors block completion
                    all_passed = False
                    all_errors.extend(errors)
                else:
                    # Non-strict mode: errors are warnings only
                    warnings_only.extend([f"[宽松模式] {e}" for e in errors])
        
        # Strict check for required outputs (Lovable workflow pattern)
        # This check is always strict, regardless of quality gate settings
        required_output_errors = self._check_required_outputs(stage)
        if required_output_errors:
            all_passed = False
            all_errors.extend(required_output_errors)
        
        if all_passed:
            self.executor.complete_stage(stage_id)
            self._auto_save_state()
            # Update vibe context
            if self.auto_save_state:
                self.update_vibe_context()
            # Return warnings if any (but stage still completes)
            return True, warnings_only
        else:
            self.executor.state.stage_status[stage_id] = StageStatus.BLOCKED
            self._auto_save_state()  # Save blocked state too
            # Update vibe context even on failure
            if self.auto_save_state:
                self.update_vibe_context()
            # Include warnings in error output
            all_errors.extend(warnings_only)
            return False, all_errors
    
    def _check_required_outputs(self, stage: Stage) -> List[str]:
        """
        Check if all required outputs exist. This is a strict check that always blocks
        stage completion if required outputs are missing (Lovable workflow pattern).
        
        Args:
            stage: Stage definition with outputs configuration
            
        Returns:
            List of error messages for missing required outputs
        """
        errors = []
        if not stage.outputs:
            return errors
        
        for output in stage.outputs:
            if not output.required:
                continue  # Skip optional outputs
            
            # Determine output path based on type
            if output.type in ("document", "report"):
                output_path = self.workspace_path / ".workflow" / "temp" / output.name
            else:
                output_path = self.workspace_path / output.name
            
            if not output_path.exists():
                errors.append(
                    f"必需输出 '{output.name}' ({output.type}) 未生成。"
                    f"路径: {output_path.relative_to(self.workspace_path)}"
                )
        
        return errors
    
    def validate_action(self, role_id: str, action: str) -> bool:
        """Validate if action is allowed for role"""
        return self.role_manager.validate_action(role_id, action)
    
    def get_current_stage(self) -> Optional[Stage]:
        """Get current stage"""
        if self.executor:
            return self.executor.get_current_stage()
        return None
    
    def get_stage_status(self, stage_id: str) -> Optional[StageStatus]:
        """Get status of a stage"""
        if self.executor:
            return self.executor.get_stage_status(stage_id)
        return None
    
    def reset_state(self) -> None:
        """
        Reset workflow execution state to initial state.
        This clears all stage statuses and starts from a clean state.
        Useful for ensuring each workflow execution is independent.
        """
        if self.executor:
            self.executor.reset_state()
            self._auto_save_state()

    def generate_team_context_md(self) -> str:
        """Generate TEAM_CONTEXT.md content for AI awareness"""
        if not self.workflow or not self.executor:
            return "# Team Context\n\nWorkflow not initialized.\n"
        
        current_stage = self.get_current_stage()
        current_role_id = self.executor.state.current_role if self.executor else None
        
        lines = ["# Team Context - Current Workflow State\n"]
        lines.append(f"**Generated**: {self._get_timestamp()}\n")
        
        # Current State
        if current_stage:
            lines.append("## Current Active Stage\n")
            lines.append(f"- **Stage**: {current_stage.name} (`{current_stage.id}`)")
            lines.append(f"- **Role**: {current_role_id or 'None'}")
            lines.append(f"- **Order**: {current_stage.order}\n")
            
            # Role constraints
            if current_role_id:
                role = self.role_manager.get_role(current_role_id)
                if role:
                    lines.append("### Role Constraints\n")
                    allowed = role.constraints.get('allowed_actions', [])
                    forbidden = role.constraints.get('forbidden_actions', [])
                    
                    if allowed:
                        lines.append("**Allowed Actions:**")
                        for action in allowed:
                            lines.append(f"- ✅ `{action}`")
                        lines.append("")
                    
                    if forbidden:
                        lines.append("**Forbidden Actions:**")
                        for action in forbidden:
                            lines.append(f"- ❌ `{action}`")
                        lines.append("")
                    
                    # Required skills
                    if role.required_skills:
                        lines.append("### Required Skills\n")
                        for req in role.required_skills:
                            skill = self.role_manager.skill_library.get(req.skill_id) if self.role_manager.skill_library else None
                            if skill:
                                lines.append(f"- **{skill.name}** (Level ≥{req.min_level})")
                                if skill.tools:
                                    lines.append(f"  - Tools: {', '.join(skill.tools)}")
                            else:
                                lines.append(f"- `{req.skill_id}` (Level ≥{req.min_level})")
                        lines.append("")
            
            # Stage requirements
            lines.append("### Stage Requirements\n")
            if current_stage.outputs:
                lines.append("**Required Outputs:**")
                for output in current_stage.outputs:
                    # 文档类型输出在临时目录
                    if output.type == "document" or output.type == "report":
                        output_path = self.workspace_path / ".workflow" / "temp" / output.name
                    else:
                        output_path = self.workspace_path / output.name
                    marker = "✅" if output_path.exists() else "⏳"
                    lines.append(f"- {marker} `{output.name}` ({output.type}, required={output.required})")
                lines.append("")
            
            if current_stage.quality_gates:
                lines.append("**Quality Gates:**")
                for gate in current_stage.quality_gates:
                    lines.append(f"- `{gate.type}`: {', '.join(gate.criteria)}")
                lines.append("")
        else:
            lines.append("## Current Active Stage\n")
            lines.append("- **Status**: No active stage\n")
            lines.append("**Action Required**: Run `workflow start <stage> <role>` to begin.\n")
        
        # Workflow Overview
        lines.append("## Workflow Overview\n")
        lines.append(f"- **Workflow**: {self.workflow.name}")
        lines.append(f"- **Total Stages**: {len(self.workflow.stages)}\n")
        
        completed = self.executor.get_completed_stages() if self.executor else set()
        lines.append("### Stage Status\n")
        for stage in self.workflow.stages:
            status = self.get_stage_status(stage.id)
            status_icon = "✅" if stage.id in completed else ("🔄" if status == StageStatus.IN_PROGRESS else "⏳")
            lines.append(f"- {status_icon} **{stage.name}** (`{stage.id}`) - Role: `{stage.role}`")
        
        lines.append("\n---\n")
        lines.append("*This file is auto-generated. Do not edit manually.*")
        
        return "\n".join(lines)
    
    def update_vibe_context(self) -> Path:
        """Update TEAM_CONTEXT.md file and return its path"""
        context_file = self.workspace_path / ".workflow" / "TEAM_CONTEXT.md"
        context_file.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate_team_context_md()
        context_file.write_text(content, encoding='utf-8')
        return context_file
    
    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp string"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_mermaid(self, include_roles: bool = True) -> str:
        """Generate Mermaid flow diagram for the workflow"""
        if not self.workflow:
            return "graph TD\n  Empty[Workflow not loaded]"
            
        lines = ["graph TD"]
        
        # 1. Workflow Stages
        for stage in self.workflow.stages:
            # Stage nodes
            lines.append(f"  {stage.id}[\"{stage.name}<br/>({stage.role})\"]")
            
            # Edges from prerequisites
            for prereq in stage.prerequisites:
                lines.append(f"  {prereq} --> {stage.id}")
            
            # Implicit order edges (dashed) if no explicit prerequisites
            if not stage.prerequisites and stage.order > 1:
                prev_stages = [s for s in self.workflow.stages if s.order == stage.order - 1]
                for prev in prev_stages:
                    lines.append(f"  {prev.id} -.-> {stage.id}")
        
        # 2. Role Hierarchy (Optional)
        if include_roles:
            lines.append("\n  subgraph Roles [Role Hierarchy]")
            has_hierarchy = False
            for role_id, role in self.role_manager.roles.items():
                if role.extends:
                    has_hierarchy = True
                    for parent in role.extends:
                        lines.append(f"    {role_id} -- extends --> {parent}")
                else:
                    lines.append(f"    {role_id}")
            if not has_hierarchy:
                lines.append("    NoExplicitHierarchy[All roles are independent]")
            lines.append("  end")
            
        return "\n".join(lines)


@dataclass
class ExecutionTracker:
    """Tracks skill execution history and statistics"""
    
    def __init__(self):
        self.executions: List[SkillExecution] = []
    
    def record_execution(self, skill_execution: SkillExecution) -> None:
        """Record a skill execution"""
        self.executions.append(skill_execution)
    
    def get_skill_history(self, skill_id: str) -> List[SkillExecution]:
        """Get execution history for a specific skill"""
        return [e for e in self.executions if e.skill_id == skill_id]
    
    def get_success_rate(self, skill_id: str) -> float:
        """Calculate success rate for a skill"""
        history = self.get_skill_history(skill_id)
        if not history:
            return 0.0
        successful = sum(1 for e in history if e.status == "success")
        return successful / len(history)
    
    def get_avg_execution_time(self, skill_id: str) -> float:
        """Calculate average execution time for a skill"""
        history = self.get_skill_history(skill_id)
        if not history:
            return 0.0
        total_time = sum(e.execution_time for e in history)
        return total_time / len(history)
    
    def get_total_executions(self, skill_id: Optional[str] = None) -> int:
        """Get total number of executions, optionally filtered by skill_id"""
        if skill_id:
            return len(self.get_skill_history(skill_id))
        return len(self.executions)
    
    def export_trace(self, format: str = "json") -> str:
        """Export execution trace in specified format"""
        if format == "json":
            executions_dict = [
                {
                    "skill_id": e.skill_id,
                    "input": e.input,
                    "output": e.output,
                    "status": e.status,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "execution_time": e.execution_time,
                    "timestamp": e.timestamp.isoformat(),
                    "retry_count": e.retry_count,
                    "stage_id": e.stage_id,
                    "role_id": e.role_id,
                }
                for e in self.executions
            ]
            return json.dumps(executions_dict, indent=2, default=str)
        elif format == "yaml":
            executions_dict = [
                {
                    "skill_id": e.skill_id,
                    "input": e.input,
                    "output": e.output,
                    "status": e.status,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "execution_time": e.execution_time,
                    "timestamp": e.timestamp.isoformat(),
                    "retry_count": e.retry_count,
                    "stage_id": e.stage_id,
                    "role_id": e.role_id,
                }
                for e in self.executions
            ]
            return yaml.dump(executions_dict, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics"""
        skill_ids = set(e.skill_id for e in self.executions)
        skills_stats: Dict[str, Any] = {}
        stats: Dict[str, Any] = {
            "total_executions": len(self.executions),
            "unique_skills": len(skill_ids),
            "skills": skills_stats
        }
        
        for skill_id in skill_ids:
            history = self.get_skill_history(skill_id)
            skills_stats[skill_id] = {
                "total_executions": len(history),
                "success_rate": self.get_success_rate(skill_id),
                "avg_execution_time": self.get_avg_execution_time(skill_id),
                "total_retries": sum(e.retry_count for e in history),
            }
        
        return stats


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
        
        # Check error types that are retryable
        error_types = error_config.get('error_types', [])
        if not error_types:
            return False
        
        # Determine error type from exception
        error_type = self._classify_error(error)
        
        # Check if this error type is retryable
        for et_config in error_types:
            if isinstance(et_config, dict):
                if et_config.get('type') == error_type.value:
                    return bool(et_config.get('retryable', False))
            elif isinstance(et_config, str):
                # Simple string format: "error_type:retryable"
                if error_type.value in et_config:
                    return True
        
        return False
    
    def get_retry_delay(self, retry_count: int, strategy: str = "exponential_backoff") -> float:
        """Calculate retry delay based on strategy"""
        if strategy == "exponential_backoff":
            return float(min(2 ** retry_count, 60.0))  # Max 60 seconds
        elif strategy == "linear_backoff":
            return float(min(retry_count * 2, 60.0))  # Max 60 seconds
        elif strategy == "fixed_delay":
            return 1.0  # Fixed 1 second delay
        else:
            return 1.0  # Default 1 second


class IntentRouter:
    """
    意图路由器：根据用户输入智能识别需要执行的阶段
    
    支持两种模式：
    1. LLM模式（优先）：使用LLM理解用户意图
    2. 规则引擎模式（回退）：基于关键词匹配（无LLM时使用）
    """
    
    def __init__(self, engine: 'WorkflowEngine', llm_client: Optional[Any] = None):
        self.engine = engine
        self.llm_client = llm_client
        self.llm_enabled = llm_client is not None
    
    def analyze_intent(self, user_input: str, use_llm: Optional[bool] = None) -> Dict[str, Any]:
        """
        分析用户意图，返回需要执行的阶段列表
        
        Args:
            user_input: 用户输入的自然语言描述
            use_llm: 是否使用LLM（None=自动选择，True=强制LLM，False=强制规则引擎）
        
        Returns:
            {
                "stages": [stage_ids],
                "confidence": float,  # 0.0-1.0
                "reasoning": str,
                "intent_type": str,  # "full", "partial", "specific"
                "method": str  # "llm" or "rule_based"
            }
        """
        if not self.engine.workflow:
            return {
                "stages": [],
                "confidence": 0.0,
                "reasoning": "工作流未加载",
                "intent_type": "unknown",
                "method": "none"
            }
        
        # 自动选择：如果有LLM且输入较复杂，使用LLM
        if use_llm is None:
            use_llm = self.llm_enabled and self._should_use_llm(user_input)
        
        # LLM模式
        if use_llm and self.llm_enabled:
            return self._analyze_with_llm(user_input)
        else:
            # 规则引擎模式（回退）
            return self._analyze_with_rules(user_input)
    
    def _should_use_llm(self, user_input: str) -> bool:
        """判断是否应该使用LLM（基于输入复杂度）"""
        # 简单关键词 -> 规则引擎
        simple_keywords = ["需求", "架构", "实现", "测试", "requirements", "architecture", "implementation"]
        if any(kw in user_input.lower() for kw in simple_keywords) and len(user_input) < 50:
            return False
        
        # 复杂描述 -> LLM
        return len(user_input) > 30 or len(user_input.split()) > 5
    
    def _analyze_with_llm(self, user_input: str) -> Dict[str, Any]:
        """使用LLM分析用户意图"""
        try:
            # 构建意图识别提示
            prompt = self._build_intent_prompt(user_input)
            
            # 调用LLM
            response = self._call_llm(prompt)
            
            # 解析LLM响应
            result = self._parse_llm_response(response, user_input)
            result["method"] = "llm"
            
            return result
            
        except Exception as e:
            # LLM失败时回退到规则引擎
            result = self._analyze_with_rules(user_input)
            result["method"] = "rule_based_fallback"
            result["reasoning"] = f"LLM分析失败，使用规则引擎: {str(e)}"
            return result
    
    def _build_intent_prompt(self, user_input: str) -> str:
        """构建LLM意图识别提示"""
        # 获取所有阶段信息
        stages_info = []
        for stage in self.engine.workflow.stages:
            role = self.engine.role_manager.get_role(stage.role)
            role_name = role.name if role else stage.role
            
            stages_info.append(f"""
- Stage ID: {stage.id}
  Name: {stage.name}
  Role: {role_name}
  Goal: {stage.goal_template or 'N/A'}
  Description: {role.description if role else 'N/A'}
""")
        
        prompt = f"""你是一个工作流意图识别专家。根据用户的输入，分析需要执行哪些工作流阶段。

可用阶段：
{''.join(stages_info)}

用户输入："{user_input}"

请分析用户意图，并返回JSON格式：
{{
    "stages": ["stage_id1", "stage_id2", ...],  // 需要执行的阶段ID列表
    "confidence": 0.85,  // 置信度 0.0-1.0
    "reasoning": "用户想要实现新功能并测试，需要implementation和validation阶段",
    "intent_type": "partial"  // "full"=完整流程, "partial"=部分阶段, "specific"=单个阶段
}}

注意：
1. 只返回需要的阶段，不要包含不必要的阶段
2. 如果用户明确要求"完整流程"、"全部"、"end-to-end"等，返回所有阶段
3. 必须考虑阶段依赖关系（如果阶段B依赖阶段A，且B被选中，则A也必须被包含）
4. confidence应该反映你对意图理解的把握程度
5. 如果用户只是询问或查看，stages可以为空数组

只返回JSON，不要其他内容。"""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        if hasattr(self.llm_client, 'chat'):
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.chat(messages)
            # 处理不同LLM响应格式
            if isinstance(response, dict):
                return response.get('content', response.get('text', str(response)))
            return str(response)
        elif hasattr(self.llm_client, 'complete'):
            response = self.llm_client.complete(prompt, max_tokens=500)
            return str(response)
        elif callable(self.llm_client):
            return str(self.llm_client(prompt))
        else:
            raise ValueError("LLM client interface not supported")
    
    def _parse_llm_response(self, response: str, user_input: str) -> Dict[str, Any]:
        """解析LLM响应"""
        import re
        
        # 尝试提取JSON
        json_match = re.search(r'\{[^{}]*"stages"[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                # 如果JSON解析失败，尝试修复常见问题
                json_str = json_match.group()
                json_str = re.sub(r',\s*}', '}', json_str)  # 移除尾随逗号
                json_str = re.sub(r',\s*]', ']', json_str)
                try:
                    result = json.loads(json_str)
                except:
                    result = self._fallback_parse(response)
        else:
            result = self._fallback_parse(response)
        
        # 验证和修复结果
        if "stages" not in result:
            result["stages"] = []
        
        # 确保阶段ID有效
        valid_stages = []
        for stage_id in result.get("stages", []):
            if self._get_stage_by_id(stage_id):
                valid_stages.append(stage_id)
        result["stages"] = valid_stages
        
        # 解析依赖关系
        result["stages"] = self._resolve_dependencies(result["stages"])
        
        # 确保有置信度
        if "confidence" not in result:
            result["confidence"] = 0.7 if result["stages"] else 0.3
        
        # 确定意图类型
        if not result["stages"]:
            result["intent_type"] = "none"
        elif len(result["stages"]) == len(self.engine.workflow.stages):
            result["intent_type"] = "full"
        elif len(result["stages"]) == 1:
            result["intent_type"] = "specific"
        else:
            result["intent_type"] = "partial"
        
        # 生成推理说明
        if "reasoning" not in result or not result["reasoning"]:
            result["reasoning"] = self._generate_reasoning(
                result["stages"], 
                result["intent_type"]
            )
        
        return result
    
    def _fallback_parse(self, response: str) -> Dict[str, Any]:
        """LLM响应解析失败时的回退处理"""
        # 尝试从文本中提取阶段ID
        stages = []
        for stage in self.engine.workflow.stages:
            if stage.id.lower() in response.lower() or stage.name.lower() in response.lower():
                stages.append(stage.id)
        
        return {
            "stages": stages,
            "confidence": 0.5,
            "reasoning": "LLM响应解析失败，使用文本匹配",
            "intent_type": "partial" if stages else "unknown"
        }
    
    def _analyze_with_rules(self, user_input: str) -> Dict[str, Any]:
        """使用规则引擎分析（关键词匹配）"""
        user_input_lower = user_input.lower()
        
        # 1. 检测@[team] - 总是执行完整工作流
        if "@[team]" in user_input or "@team" in user_input:
            return {
                "stages": [s.id for s in self.engine.workflow.stages],
                "confidence": 1.0,
                "reasoning": "检测到@[team]，虚拟团队工作流执行完整流程",
                "intent_type": "full",
                "method": "rule_based"
            }
        
        # 2. 检测完整流程意图
        full_workflow_keywords = [
            "完整", "全部", "整个", "end-to-end", "e2e", 
            "从头", "全流程", "wfauto", "完整工作流"
        ]
        if any(kw in user_input_lower for kw in full_workflow_keywords):
            return {
                "stages": [s.id for s in self.engine.workflow.stages],
                "confidence": 1.0,
                "reasoning": "检测到完整流程请求",
                "intent_type": "full",
                "method": "rule_based"
            }
        
        # 3. 检测明确指定部分阶段的请求
        explicit_partial_keywords = ["只做", "只要", "仅", "only", "just", "跳过", "不要", "不需要"]
        is_explicit_partial = any(kw in user_input_lower for kw in explicit_partial_keywords)
        
        # 如果不是明确指定部分阶段，默认返回完整工作流（虚拟团队工作流特性）
        if not is_explicit_partial:
            # 检测是否有任务描述（实现、开发、创建等）
            task_keywords = ["实现", "开发", "创建", "构建", "做", "完成", "implement", "develop", "create", "build", "make"]
            has_task = any(kw in user_input_lower for kw in task_keywords)
            
            # 如果有任务描述或输入足够长，默认执行完整工作流
            if has_task or len(user_input.strip()) > 10:
                return {
                    "stages": [s.id for s in self.engine.workflow.stages],
                    "confidence": 0.9,
                    "reasoning": "虚拟团队工作流：默认执行完整工作流分析需求目标",
                    "intent_type": "full",
                    "method": "rule_based"
                }
        
        # 4. 阶段关键词匹配（仅在明确指定部分阶段时使用）
        stage_matches = self._match_stages_by_keywords(user_input_lower)
        
        # 5. 角色关键词匹配
        role_matches = self._match_stages_by_roles(user_input_lower)
        
        # 6. 合并匹配结果
        matched_stage_ids = set(stage_matches) | set(role_matches)
        
        # 7. 如果没有匹配，检查是否有特定任务类型
        if not matched_stage_ids:
            matched_stage_ids = self._match_by_task_type(user_input_lower)
        
        # 8. 包含依赖阶段
        required_stages = self._resolve_dependencies(list(matched_stage_ids))
        
        # 9. 如果明确指定部分阶段但匹配结果为空，仍然返回完整工作流
        if is_explicit_partial and not required_stages:
            return {
                "stages": [s.id for s in self.engine.workflow.stages],
                "confidence": 0.7,
                "reasoning": "未匹配到明确阶段，执行完整工作流",
                "intent_type": "full",
                "method": "rule_based"
            }
        
        # 10. 计算置信度
        confidence = self._calculate_confidence(
            list(matched_stage_ids), 
            user_input_lower,
            len(required_stages) < len(self.engine.workflow.stages)
        )
        
        # 11. 确定意图类型
        intent_type = "full" if len(required_stages) == len(self.engine.workflow.stages) else (
            "specific" if len(required_stages) == 1 else "partial"
        )
        
        return {
            "stages": sorted(required_stages, key=lambda sid: self._get_stage_order(sid)),
            "confidence": confidence,
            "reasoning": self._generate_reasoning(list(matched_stage_ids), required_stages, intent_type),
            "intent_type": intent_type,
            "method": "rule_based"
        }
    
    def _match_stages_by_keywords(self, user_input: str) -> List[str]:
        """基于阶段名称和关键词匹配"""
        matched = []
        
        # 阶段关键词映射
        stage_keywords = {
            "requirements": ["需求", "要求", "范围", "scope", "requirement", "spec", "规范"],
            "architecture": ["架构", "设计", "architecture", "design", "schema", "dsl", "结构"],
            "implementation": ["实现", "编码", "代码", "implement", "code", "开发", "编写"],
            "validation": ["验证", "测试", "质量", "validation", "test", "qa", "review", "检查"]
        }
        
        for stage in self.engine.workflow.stages:
            stage_id_lower = stage.id.lower()
            stage_name_lower = stage.name.lower()
            
            # 检查阶段ID和名称
            if stage_id_lower in user_input or stage_name_lower in user_input:
                matched.append(stage.id)
                continue
            
            # 检查关键词
            keywords = stage_keywords.get(stage.id, [])
            if any(kw in user_input for kw in keywords):
                matched.append(stage.id)
        
        return matched
    
    def _match_stages_by_roles(self, user_input: str) -> List[str]:
        """基于角色描述匹配"""
        matched = []
        
        for stage in self.engine.workflow.stages:
            role = self.engine.role_manager.get_role(stage.role)
            if not role:
                continue
            
            # 检查角色名称和描述
            role_name_lower = role.name.lower()
            role_desc_lower = role.description.lower()
            
            if role_name_lower in user_input or role_desc_lower in user_input:
                matched.append(stage.id)
                continue
            
            # 检查角色允许的动作
            allowed_actions = role.constraints.get('allowed_actions', [])
            for action in allowed_actions:
                if action.lower() in user_input:
                    matched.append(stage.id)
                    break
        
        return matched
    
    def _match_by_task_type(self, user_input: str) -> List[str]:
        """基于任务类型推断阶段"""
        matched = []
        
        # 文档相关 -> requirements/architecture
        if any(kw in user_input for kw in ["文档", "doc", "写文档", "创建文档"]):
            matched.extend(["requirements", "architecture"])
        
        # 代码相关 -> implementation
        if any(kw in user_input for kw in ["代码", "code", "写代码", "实现功能"]):
            matched.append("implementation")
        
        # 测试相关 -> validation
        if any(kw in user_input for kw in ["测试", "test", "验证", "检查代码"]):
            matched.append("validation")
        
        # 过滤无效的阶段ID
        valid_matched = []
        for stage_id in matched:
            if self._get_stage_by_id(stage_id):
                valid_matched.append(stage_id)
        
        return valid_matched
    
    def _resolve_dependencies(self, stage_ids: List[str]) -> List[str]:
        """解析阶段依赖，确保前置阶段被包含"""
        required = set(stage_ids)
        
        # 递归解析依赖
        changed = True
        while changed:
            changed = False
            for stage_id in list(required):
                stage = self._get_stage_by_id(stage_id)
                if stage and stage.prerequisites:
                    for prereq in stage.prerequisites:
                        if prereq not in required:
                            required.add(prereq)
                            changed = True
        
        return list(required)
    
    def _calculate_confidence(
        self, 
        matched_stages: List[str], 
        user_input: str,
        is_partial: bool
    ) -> float:
        """计算匹配置信度"""
        if not matched_stages:
            return 0.0
        
        # 基础置信度
        confidence = 0.5
        
        # 如果匹配到多个阶段，增加置信度
        if len(matched_stages) > 1:
            confidence += 0.2
        
        # 如果输入包含明确的阶段名称，增加置信度
        for stage in self.engine.workflow.stages:
            if stage.id.lower() in user_input or stage.name.lower() in user_input:
                confidence += 0.2
                break
        
        # 如果是部分匹配，稍微降低置信度（因为可能遗漏）
        if is_partial:
            confidence -= 0.1
        
        return min(1.0, max(0.0, confidence))
    
    def _generate_reasoning(
        self, 
        matched: List[str], 
        required: List[str],
        intent_type: str
    ) -> str:
        """生成推理说明"""
        if intent_type == "full":
            return "执行完整工作流（所有阶段）"
        
        matched_names = [self._get_stage_name(sid) for sid in matched]
        required_names = [self._get_stage_name(sid) for sid in required]
        
        if len(matched) == len(required):
            return f"匹配到阶段: {', '.join(matched_names)}"
        else:
            return f"匹配到阶段: {', '.join(matched_names)}，包含依赖: {', '.join(required_names)}"
    
    def _get_stage_by_id(self, stage_id: str) -> Optional[Stage]:
        """获取阶段对象"""
        if not self.engine.executor:
            return None
        return self.engine.executor._get_stage_by_id(stage_id)
    
    def _get_stage_order(self, stage_id: str) -> int:
        """获取阶段顺序"""
        stage = self._get_stage_by_id(stage_id)
        return stage.order if stage else 999
    
    def _get_stage_name(self, stage_id: str) -> str:
        """获取阶段名称"""
        stage = self._get_stage_by_id(stage_id)
        return stage.name if stage else stage_id
    
    def handle_retry(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        error: Exception,
        skill: Skill
    ) -> Dict[str, Any]:
        """Handle retry logic and return retry configuration"""
        if not skill.error_handling:
            raise error  # No retry configured, re-raise
        
        error_config = skill.error_handling
        strategy = error_config.get('retry_strategy', 'exponential_backoff')
        
        # Get current retry count from tracker if available
        retry_count = 0
        if self.execution_tracker:
            history = self.execution_tracker.get_skill_history(skill_id)
            retry_count = max((e.retry_count for e in history), default=0) + 1
        
        delay = self.get_retry_delay(retry_count, strategy)
        
        return {
            "should_retry": True,
            "retry_count": retry_count,
            "delay": delay,
            "strategy": strategy
        }
    
    def _classify_error(self, error: Exception) -> SkillErrorType:
        """Classify exception into SkillErrorType"""
        error_msg = str(error).lower()
        error_type = type(error).__name__.lower()
        
        if 'validation' in error_msg or 'schema' in error_msg:
            return SkillErrorType.VALIDATION_ERROR
        elif 'timeout' in error_msg or 'time' in error_type:
            return SkillErrorType.TIMEOUT_ERROR
        elif 'test' in error_msg or 'test' in error_type:
            return SkillErrorType.TEST_FAILURE
        elif 'context' in error_msg or 'missing' in error_msg:
            return SkillErrorType.INSUFFICIENT_CONTEXT
        else:
            return SkillErrorType.EXECUTION_ERROR
    
    def format_error_response(
        self,
        error: Exception,
        skill: Skill,
        retryable: bool = False
    ) -> Dict[str, Any]:
        """Format error response in standard format"""
        error_type = self._classify_error(error)
        
        response = {
            "success": False,
            "error_type": error_type.value,
            "error_message": str(error),
            "retryable": retryable,
        }
        
        # Add suggested fix if available in skill metadata
        if skill.metadata and 'error_suggestions' in skill.metadata:
            suggestions = skill.metadata['error_suggestions']
            if isinstance(suggestions, dict) and error_type.value in suggestions:
                response["suggested_fix"] = suggestions[error_type.value]
        
        return response


@dataclass
class AgentContext:
    """Context for Agent execution"""
    goal: str
    workspace_path: Path
    project_context: Optional[ProjectContext] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    decisions: List[str] = field(default_factory=list)


@dataclass
class ContextSummary:
    """
    Lightweight context summary for token optimization.
    
    Instead of passing full context history (which can be thousands of tokens),
    this class only stores key information summaries.
    """
    stage_summary: str  # Summary of completed stages: "需求分析完成 → PRD生成完成"
    key_outputs: List[str]  # Only output file names, not content
    current_goal: str  # Current stage goal
    completed_stages: List[str]  # List of completed stage IDs
    current_role: Optional[str] = None
    
    def to_text(self) -> str:
        """Convert summary to text format for LLM prompts"""
        parts = []
        if self.stage_summary:
            parts.append(f"阶段摘要: {self.stage_summary}")
        if self.key_outputs:
            parts.append(f"关键输出: {', '.join(self.key_outputs)}")
        if self.current_goal:
            parts.append(f"当前目标: {self.current_goal}")
        return "\n".join(parts)
    
    @classmethod
    def from_engine(cls, engine: 'WorkflowEngine', current_stage_id: Optional[str] = None) -> 'ContextSummary':
        """Create context summary from WorkflowEngine"""
        if not engine.executor:
            return cls(
                stage_summary="工作流未初始化",
                key_outputs=[],
                current_goal="",
                completed_stages=[],
                current_role=None
            )
        
        completed = engine.executor.get_completed_stages()
        current = engine.executor.state.current_role
        
        # Build stage summary
        stage_names = []
        for stage_id in sorted(completed):
            stage = engine.executor._get_stage_by_id(stage_id)
            if stage:
                stage_names.append(stage.name)
        
        stage_summary = " → ".join(stage_names) if stage_names else "无已完成阶段"
        if current_stage_id:
            current_stage = engine.executor._get_stage_by_id(current_stage_id)
            if current_stage:
                stage_summary += f" → {current_stage.name} (进行中)"
        
        # Get key outputs (only file names)
        key_outputs = []
        for stage_id in completed:
            stage = engine.executor._get_stage_by_id(stage_id)
            if stage and stage.outputs:
                for output in stage.outputs:
                    # 文档类型输出在临时目录
                    if output.type == "document" or output.type == "report":
                        output_path = engine.workspace_path / ".workflow" / "temp" / output.name
                    else:
                        output_path = engine.workspace_path / output.name
                    if output_path.exists():
                        key_outputs.append(output.name)
        
        # Get current goal
        current_goal = ""
        if current_stage_id:
            stage = engine.executor._get_stage_by_id(current_stage_id)
            if stage:
                current_goal = stage.goal_template or stage.name
        
        return cls(
            stage_summary=stage_summary,
            key_outputs=key_outputs,
            current_goal=current_goal,
            completed_stages=list(completed),
            current_role=current
        )


class Agent:
    """
    Represents a Role in action, capable of executing tasks.
    
    IMPORTANT: This class handles the Reasoning Layer only.
    Skills MUST NOT be used in reasoning methods (prepare, make_decision, generate_prompt).
    Skills should only be invoked through AgentOrchestrator.execute_skill() in the Skill Invocation Layer.
    
    Architecture:
    - Reasoning Layer (this class): Task understanding, goal clarification, strategy, decisions
    - Skill Invocation Layer (AgentOrchestrator): Skill selection and execution
    - Execution Layer: Tool/API execution
    """
    def __init__(self, role: Role, engine: 'WorkflowEngine', skill_selector: Optional[SkillSelector] = None):
        self.role = role
        self.engine = engine
        self.context: Optional[AgentContext] = None
        # Note: skill_selector is stored but NOT used in reasoning methods
        # It's only available for external skill selection queries, not for reasoning
        self.skill_selector = skill_selector or SkillSelector(engine)

    def prepare(self, goal: str, inputs: Optional[Dict[str, Any]] = None):
        """
        Prepare agent for task execution (Reasoning Layer).
        
        This is a pure reasoning method - NO skills should be invoked here.
        Skills are invoked separately through AgentOrchestrator.execute_skill().
        """
        self.context = AgentContext(
            goal=goal,
            workspace_path=self.engine.workspace_path,
            project_context=self.engine.context,
            inputs=inputs or {}
        )

    def make_decision(self, decision: str):
        """
        Record a decision made by the agent (Reasoning Layer).
        
        This is a pure reasoning method - NO skills should be invoked here.
        Decisions are made through natural language reasoning, not skill execution.
        """
        if self.context:
            self.context.decisions.append(decision)
            print(f"💭 Agent Decision: {decision}")

    def produce_output(self, name: str, content: str, output_type: str = "code"):
        """
        Produce an output file
        
        Args:
            name: Output file name
            content: File content
            output_type: Type of output ("document", "report", "code", etc.)
                        Documents and reports are saved to .workflow/temp/ to avoid cluttering the project
        """
        if not self.context:
            raise ValueError("Agent not prepared")
        
        # 文档和报告类型生成到临时目录，避免侵入项目
        if output_type in ("document", "report"):
            path = self.engine.workspace_path / ".workflow" / "temp" / name
        else:
            path = self.engine.workspace_path / name
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        self.context.outputs[name] = str(path)
        
        if output_type in ("document", "report"):
            print(f"📄 Agent produced output (temp): {name} -> {path.relative_to(self.engine.workspace_path)}")
        else:
            print(f"📄 Agent produced output: {name}")

    def get_context_summary(self, stage_id: Optional[str] = None) -> ContextSummary:
        """
        Get lightweight context summary for token optimization.
        
        Returns only key information, not full context history.
        This is much more token-efficient than passing full context.
        """
        return ContextSummary.from_engine(self.engine, stage_id)
    
    def generate_prompt(self, stage: Stage, use_summary: bool = True) -> str:
        """
        Generate a structured prompt for the LLM based on role and stage (Reasoning Layer).
        
        IMPORTANT: This prompt is for reasoning only - it does NOT include skill information.
        Skills are selected and executed separately in the Skill Invocation Layer.
        
        The prompt focuses on:
        - Role identity and constraints
        - Task understanding and goal clarification
        - Strategy and decision-making guidance
        - Expected outputs (but NOT how to achieve them via skills)
        
        Args:
            stage: Stage to generate prompt for
            use_summary: If True, use lightweight context summary instead of full context
        """
        if not self.context:
            raise ValueError("Agent not prepared. Call prepare() first.")
            
        # 1. Base Identity
        prompt = [f"You are acting as a {self.role.name}."]
        prompt.append(f"Description: {self.role.description}\n")
        
        # 2. Constraints
        allowed = self.role.constraints.get('allowed_actions', [])
        forbidden = self.role.constraints.get('forbidden_actions', [])
        if allowed:
            prompt.append("ALLOWED ACTIONS: " + ", ".join(allowed))
        if forbidden:
            prompt.append("FORBIDDEN ACTIONS: " + ", ".join(forbidden))
        prompt.append("")
        
        # 3. Context Summary (lightweight)
        if use_summary:
            context_summary = self.get_context_summary(stage.id)
            if context_summary.stage_summary:
                prompt.append("WORKFLOW CONTEXT:")
                prompt.append(context_summary.to_text())
                prompt.append("")
        
        # 4. Stage Goal
        prompt.append(f"CURRENT STAGE: {stage.name}")
        goal_text = stage.goal_template or self.context.goal
        prompt.append(f"GOAL: {goal_text}\n")
        
        # 5. Expected Outputs
        if stage.outputs:
            prompt.append("REQUIRED OUTPUTS:")
            for output in stage.outputs:
                prompt.append(f"- {output.name} ({output.type})")
            prompt.append("")
            
        # 6. Role-Specific Instructions
        if self.role.instruction_template:
            prompt.append("INSTRUCTIONS:")
            prompt.append(self.role.instruction_template)
        
        # 7. Reasoning Guidance (explicitly exclude skills)
        prompt.append("")
        prompt.append("REASONING GUIDANCE:")
        prompt.append("- Focus on understanding the task, clarifying goals, and making strategic decisions")
        prompt.append("- Do NOT invoke specific skills or tools during reasoning")
        prompt.append("- Skills will be selected and executed separately based on your decisions")
        prompt.append("- Use natural language reasoning and chain-of-thought")
            
        return "\n".join(prompt)


# ============================================================================
# Skill Invoker System - 可扩展的技能调用接口
# ============================================================================

class SkillInvoker(ABC):
    """
    Abstract base class for skill invocation.
    
    Provides a pluggable interface for different skill execution backends:
    - LLM-based execution
    - Tool/Function execution
    - External API calls
    - Custom implementations
    """
    
    @abstractmethod
    def invoke(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke a skill with the given input data.
        
        Args:
            skill: The skill definition to execute
            input_data: Input data for the skill
            context: Optional execution context
            
        Returns:
            Dict containing execution result with at least:
            - success: bool
            - output: Dict[str, Any] (if successful)
            - error: str (if failed)
        """
        pass
    
    @abstractmethod
    def supports_skill(self, skill: Skill) -> bool:
        """Check if this invoker can handle the given skill"""
        pass


class PlaceholderSkillInvoker(SkillInvoker):
    """
    Default placeholder implementation for skill invocation.
    
    Returns mock results - useful for testing workflow structure.
    """
    
    def invoke(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Placeholder implementation that returns mock success"""
        # Generate mock output based on skill's output_schema
        output = {}
        if skill.output_schema and 'properties' in skill.output_schema:
            for prop_name, prop_def in skill.output_schema['properties'].items():
                output[prop_name] = f"[mock_{prop_name}]"
        else:
            output = {"result": f"Skill {skill.id} executed successfully"}
        
        return {
            "success": True,
            "output": output,
            "message": f"Placeholder execution of skill '{skill.name}'"
        }
    
    def supports_skill(self, skill: Skill) -> bool:
        """Placeholder supports all skills"""
        return True


class LLMSkillInvoker(SkillInvoker):
    """
    LLM-based skill invoker.
    
    Uses an LLM client to execute skills by generating appropriate prompts
    and parsing the responses according to skill schemas.
    """
    
    def __init__(self, llm_client: Any, max_tokens: int = 4096):
        """
        Initialize LLM skill invoker.
        
        Args:
            llm_client: LLM client with a 'complete' or 'chat' method
            max_tokens: Maximum tokens for LLM response
        """
        self.llm_client = llm_client
        self.max_tokens = max_tokens
    
    def invoke(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute skill using LLM"""
        prompt = self._generate_prompt(skill, input_data, context)
        
        try:
            # Try different LLM client interfaces
            if hasattr(self.llm_client, 'complete'):
                response = self.llm_client.complete(prompt, max_tokens=self.max_tokens)
            elif hasattr(self.llm_client, 'chat'):
                response = self.llm_client.chat([{"role": "user", "content": prompt}])
            elif callable(self.llm_client):
                response = self.llm_client(prompt)
            else:
                raise ValueError("LLM client must have 'complete', 'chat' method or be callable")
            
            # Parse response
            output = self._parse_response(response, skill)
            
            return {
                "success": True,
                "output": output,
                "raw_response": response
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "llm_execution_error"
            }
    
    def _generate_prompt(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate LLM prompt for skill execution"""
        parts = []
        
        # Skill description
        parts.append(f"# Task: Execute Skill '{skill.name}'")
        parts.append(f"\n## Description\n{skill.description}")
        
        # Dimensions
        if skill.dimensions:
            parts.append(f"\n## Skill Dimensions\n- " + "\n- ".join(skill.dimensions))
        
        # Constraints
        if skill.constraints:
            parts.append(f"\n## Constraints\n- " + "\n- ".join(skill.constraints))
        
        # Input data
        parts.append(f"\n## Input Data\n```json\n{json.dumps(input_data, indent=2)}\n```")
        
        # Expected output schema
        if skill.output_schema:
            parts.append(f"\n## Expected Output Format\n```json\n{json.dumps(skill.output_schema, indent=2)}\n```")
        
        # Context
        if context:
            parts.append(f"\n## Context\n```json\n{json.dumps(context, indent=2)}\n```")
        
        parts.append("\n## Instructions")
        parts.append("Execute the task described above and provide output in the expected format.")
        parts.append("Return your response as valid JSON matching the output schema.")
        
        return "\n".join(parts)
    
    def _parse_response(self, response: Any, skill: Skill) -> Dict[str, Any]:
        """Parse LLM response into structured output"""
        # Handle different response types
        if isinstance(response, dict):
            return cast(Dict[str, Any], response)
        
        response_str = str(response)
        
        # Try to extract JSON from response
        try:
            # Look for JSON block
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_str)
            if json_match:
                return cast(Dict[str, Any], json.loads(json_match.group(1)))
            
            # Try parsing entire response as JSON
            return cast(Dict[str, Any], json.loads(response_str))
        except json.JSONDecodeError:
            # Return as text if not valid JSON
            return {"text": response_str}
    
    def supports_skill(self, skill: Skill) -> bool:
        """LLM invoker supports all skills"""
        return True


class CompositeSkillInvoker(SkillInvoker):
    """
    Composite invoker that delegates to specialized invokers.
    
    Allows registering different invokers for different skill types.
    """
    
    def __init__(self, default_invoker: Optional[SkillInvoker] = None):
        """
        Initialize composite invoker.
        
        Args:
            default_invoker: Default invoker for unmatched skills
        """
        self.invokers: List[Tuple[Callable[[Skill], bool], SkillInvoker]] = []
        self.default_invoker = default_invoker or PlaceholderSkillInvoker()
    
    def register(
        self,
        matcher: Callable[[Skill], bool],
        invoker: SkillInvoker
    ) -> None:
        """
        Register an invoker for skills matching the condition.
        
        Args:
            matcher: Function that returns True if skill should use this invoker
            invoker: The invoker to use for matched skills
        """
        self.invokers.append((matcher, invoker))
    
    def register_for_skill_ids(
        self,
        skill_ids: List[str],
        invoker: SkillInvoker
    ) -> None:
        """Register an invoker for specific skill IDs"""
        self.register(lambda s: s.id in skill_ids, invoker)
    
    def register_for_dimensions(
        self,
        dimensions: List[str],
        invoker: SkillInvoker
    ) -> None:
        """Register an invoker for skills with specific dimensions"""
        self.register(
            lambda s: any(d in s.dimensions for d in dimensions),
            invoker
        )
    
    def invoke(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Invoke skill using the appropriate registered invoker"""
        for matcher, invoker in self.invokers:
            if matcher(skill):
                return invoker.invoke(skill, input_data, context)
        
        return self.default_invoker.invoke(skill, input_data, context)
    
    def supports_skill(self, skill: Skill) -> bool:
        """Check if any registered invoker supports the skill"""
        for matcher, invoker in self.invokers:
            if matcher(skill) and invoker.supports_skill(skill):
                return True
        return self.default_invoker.supports_skill(skill)


# ============================================================================
# Condition Evaluator - 条件表达式评估器
# ============================================================================

class ConditionEvaluator:
    """
    Evaluates condition expressions in workflow steps.
    
    Supports:
    - Step result access: step_1.result.status
    - Step output access: step_1.outputs.key
    - Workflow input access: inputs.key
    - Comparison operators: ==, !=, <, >, <=, >=
    - Logical operators: and, or, not
    - String and numeric comparisons
    """
    
    def __init__(self, step_outputs: Dict[str, Dict[str, Any]], workflow_inputs: Dict[str, Any]):
        """
        Initialize condition evaluator.
        
        Args:
            step_outputs: Dictionary mapping step_id to step outputs
            workflow_inputs: Workflow input variables
        """
        self.step_outputs = step_outputs
        self.workflow_inputs = workflow_inputs
    
    def evaluate(self, condition: str) -> bool:
        """
        Evaluate a condition expression.
        
        Args:
            condition: Condition expression string
            
        Returns:
            Boolean result of evaluation
        """
        if not condition:
            return True
        
        try:
            # Resolve variable references
            resolved_condition = self._resolve_variables(condition)
            
            # Evaluate the expression safely
            # Using eval with restricted globals for safety
            safe_dict = {
                '__builtins__': {
                    'True': True,
                    'False': False,
                    'None': None,
                    'bool': bool,
                    'int': int,
                    'float': float,
                    'str': str,
                    'len': len,
                }
            }
            
            # Replace common operators with Python equivalents
            resolved_condition = resolved_condition.replace(' and ', ' and ')
            resolved_condition = resolved_condition.replace(' or ', ' or ')
            resolved_condition = resolved_condition.replace(' not ', ' not ')
            
            result = eval(resolved_condition, safe_dict)
            return bool(result)
        except Exception as e:
            # If evaluation fails, log and return False
            warnings.warn(f"Condition evaluation failed: {condition}, error: {e}")
            return False
    
    def _resolve_variables(self, condition: str) -> str:
        """Resolve variable references in condition"""
        import re
        
        def resolve_step_ref(match):
            """Resolve step reference like step_1.result.status"""
            ref = match.group(1)
            parts = ref.split('.')
            
            if len(parts) < 2:
                return 'None'
            
            step_id = parts[0]
            if step_id not in self.step_outputs:
                return 'None'
            
            step_data = self.step_outputs[step_id]
            
            # Navigate through the data structure
            current = step_data
            for part in parts[1:]:
                if isinstance(current, dict):
                    current = current.get(part)
                elif hasattr(current, part):
                    current = getattr(current, part)
                else:
                    return 'None'
                if current is None:
                    return 'None'
            
            # Convert to Python literal
            if isinstance(current, bool):
                return str(current)
            elif isinstance(current, (int, float)):
                return str(current)
            elif isinstance(current, str):
                return repr(current)
            else:
                return repr(current)
        
        def resolve_input_ref(match):
            """Resolve input reference like inputs.key"""
            key = match.group(1)
            value = self.workflow_inputs.get(key)
            if value is None:
                return 'None'
            if isinstance(value, bool):
                return str(value)
            elif isinstance(value, (int, float)):
                return str(value)
            elif isinstance(value, str):
                return repr(value)
            else:
                return repr(value)
        
        # Resolve step references: {{step.step_id.result.field}}
        condition = re.sub(r'\{\{step\.(\w+(?:\.[\w.]+)*)\}\}', resolve_step_ref, condition)
        
        # Resolve input references: {{inputs.key}}
        condition = re.sub(r'\{\{inputs\.(\w+)\}\}', resolve_input_ref, condition)
        
        return condition


# ============================================================================
# Skill Workflow Executor - 多技能工作流执行器
# ============================================================================

class SkillWorkflowExecutor:
    """
    Executes skill workflows by orchestrating multiple skills according to their dependencies.
    
    Features:
    - DAG-based execution respecting dependencies
    - Parallel execution of independent steps
    - Variable resolution for input/output chaining
    - Retry handling for failed steps
    - Execution tracking and reporting
    """
    
    def __init__(
        self,
        engine: 'WorkflowEngine',
        skill_invoker: Optional[SkillInvoker] = None,
        execution_tracker: Optional[ExecutionTracker] = None,
        max_parallel: int = 2
    ):
        """
        Initialize workflow executor.
        
        Args:
            engine: WorkflowEngine instance
            skill_invoker: Skill invoker to use (defaults to PlaceholderSkillInvoker)
            execution_tracker: Optional execution tracker
            max_parallel: Maximum parallel step executions
        """
        self.engine = engine
        self.skill_invoker = skill_invoker or PlaceholderSkillInvoker()
        self.execution_tracker = execution_tracker or ExecutionTracker()
        self.max_parallel = max_parallel
        
        # Execution state
        self._step_outputs: Dict[str, Dict[str, Any]] = {}
        self._current_execution: Optional[SkillWorkflowExecution] = None
    
    def execute_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        stage_id: Optional[str] = None,
        role_id: Optional[str] = None
    ) -> SkillWorkflowExecution:
        """
        Execute a skill workflow.
        
        Args:
            workflow_id: ID of the workflow to execute
            inputs: Initial inputs for the workflow
            stage_id: Optional stage context
            role_id: Optional role context
            
        Returns:
            SkillWorkflowExecution record
        """
        # Get workflow definition
        workflow = self.engine.role_manager.skill_workflows.get(workflow_id)
        if not workflow:
            raise WorkflowError(f"Skill workflow '{workflow_id}' not found")
        
        # Initialize execution
        execution = SkillWorkflowExecution(
            workflow_id=workflow_id,
            status="running",
            inputs=inputs.copy()
        )
        self._current_execution = execution
        self._step_outputs = {}
        
        start_time = time.time()
        
        try:
            # Reset step states
            for step in workflow.steps:
                step.status = SkillWorkflowStepStatus.PENDING
                step.result = None
                step.error = None
            
            # Create condition evaluator
            evaluator = ConditionEvaluator(self._step_outputs, inputs)
            
            # Execute steps with support for conditions and loops
            executed_steps = set()
            step_queue = workflow.topological_sort()
            
            while step_queue:
                step = step_queue.pop(0)
                
                # Skip if already executed
                if step.step_id in executed_steps:
                    continue
                
                # Check if dependencies are met
                if not self._check_dependencies_met(step, workflow, executed_steps):
                    # Re-add to queue for later processing
                    step_queue.append(step)
                    continue
                
                # Check for early termination
                if workflow.config.fail_fast and execution.errors:
                    step.status = SkillWorkflowStepStatus.SKIPPED
                    executed_steps.add(step.step_id)
                    continue
                
                # Check step condition
                if step.condition:
                    if not evaluator.evaluate(step.condition):
                        step.status = SkillWorkflowStepStatus.SKIPPED
                        executed_steps.add(step.step_id)
                        continue
                
                # Handle loops
                if step.loop_config:
                    self._execute_loop_step(step, workflow, inputs, stage_id, role_id, evaluator)
                else:
                    # Execute step normally
                    self._execute_step(step, workflow, inputs, stage_id, role_id)
                
                # Store results
                execution.step_results[step.step_id] = {
                    "status": step.status.value,
                    "result": step.result,
                    "error": step.error,
                    "execution_time": step.execution_time,
                    "iteration_count": getattr(step, 'iteration_count', 0)
                }
                
                if step.status == SkillWorkflowStepStatus.FAILED:
                    execution.errors.append(f"Step '{step.step_id}' failed: {step.error}")
                
                # Mark as executed
                executed_steps.add(step.step_id)
                
                # Handle conditional branches
                if step.branches:
                    next_step_id = self._evaluate_branches(step, workflow, evaluator)
                    if next_step_id:
                        next_step = workflow.get_step(next_step_id)
                        if next_step and next_step_id not in executed_steps:
                            # Insert next step at the beginning of queue
                            step_queue.insert(0, next_step)
            
            # Resolve final outputs
            execution.outputs = self._resolve_workflow_outputs(workflow)
            
            # Determine final status
            failed_required = any(
                s.status == SkillWorkflowStepStatus.FAILED and s.config.required
                for s in workflow.steps
            )
            all_completed = all(
                s.status in (SkillWorkflowStepStatus.COMPLETED, SkillWorkflowStepStatus.SKIPPED)
                for s in workflow.steps
            )
            
            if failed_required:
                execution.status = "failed"
            elif all_completed:
                execution.status = "completed"
            else:
                execution.status = "partial"
            
        except Exception as e:
            execution.status = "failed"
            execution.errors.append(str(e))
        
        execution.completed_at = datetime.now()
        execution.execution_time = time.time() - start_time
        self._current_execution = None
        
        return execution
    
    def _check_dependencies_met(
        self,
        step: SkillStep,
        workflow: SkillWorkflow,
        executed_steps: Set[str]
    ) -> bool:
        """Check if all step dependencies are met"""
        for dep_id in step.depends_on:
            if dep_id not in executed_steps:
                return False
            dep_step = workflow.get_step(dep_id)
            if dep_step and dep_step.status == SkillWorkflowStepStatus.FAILED:
                # If dependency failed and step is required, mark as failed
                if step.config.required:
                    step.status = SkillWorkflowStepStatus.FAILED
                    step.error = f"Dependency '{dep_id}' failed"
                    return True
        return True
    
    def _wait_for_dependencies(
        self,
        step: SkillStep,
        workflow: SkillWorkflow
    ) -> None:
        """Wait for step dependencies to complete (legacy method)"""
        for dep_id in step.depends_on:
            dep_step = workflow.get_step(dep_id)
            if dep_step and dep_step.status not in (
                SkillWorkflowStepStatus.COMPLETED,
                SkillWorkflowStepStatus.FAILED,
                SkillWorkflowStepStatus.SKIPPED
            ):
                # In a real async implementation, we would wait here
                # For now, topological sort ensures this won't happen
                pass
    
    def _evaluate_branches(
        self,
        step: SkillStep,
        workflow: SkillWorkflow,
        evaluator: ConditionEvaluator
    ) -> Optional[str]:
        """Evaluate conditional branches and return next step ID"""
        for branch in step.branches:
            if evaluator.evaluate(branch.condition):
                return branch.target_step_id
            elif branch.else_step_id:
                return branch.else_step_id
        return None
    
    def _execute_loop_step(
        self,
        step: SkillStep,
        workflow: SkillWorkflow,
        inputs: Dict[str, Any],
        stage_id: Optional[str],
        role_id: Optional[str],
        evaluator: ConditionEvaluator
    ) -> None:
        """Execute a step with loop configuration"""
        if not step.loop_config:
            return
        
        loop_config = step.loop_config
        step.iteration_count = 0
        total_time = 0.0
        
        if loop_config.type == "while":
            # While loop: execute until condition is false
            while step.iteration_count < loop_config.max_iterations:
                condition_result = evaluator.evaluate(loop_config.condition) if loop_config.condition else True
                if not condition_result:
                    break
                
                # Execute step
                step.status = SkillWorkflowStepStatus.RUNNING
                step_start = time.time()
                self._execute_step(step, workflow, inputs, stage_id, role_id)
                step_execution_time = time.time() - step_start
                total_time += step_execution_time
                
                step.iteration_count += 1
                
                # Check if we should break on failure
                if step.status == SkillWorkflowStepStatus.FAILED and loop_config.break_on_failure:
                    break
                
                # Update step outputs for next iteration
                if step.result:
                    self._step_outputs[step.step_id] = step.result
        
        elif loop_config.type == "for_each":
            # For each loop: iterate over items
            items = self._get_loop_items(loop_config.items_source, evaluator)
            
            if not isinstance(items, list):
                step.status = SkillWorkflowStepStatus.FAILED
                step.error = f"Items source '{loop_config.items_source}' is not a list"
                return
            
            for item in items:
                if step.iteration_count >= loop_config.max_iterations:
                    break
                
                # Add current item to inputs
                loop_inputs = inputs.copy()
                loop_inputs["_loop_item"] = item
                loop_inputs["_loop_index"] = step.iteration_count
                
                # Execute step
                step.status = SkillWorkflowStepStatus.RUNNING
                step_start = time.time()
                self._execute_step(step, workflow, loop_inputs, stage_id, role_id)
                step_execution_time = time.time() - step_start
                total_time += step_execution_time
                
                step.iteration_count += 1
                
                # Check if we should break on failure
                if step.status == SkillWorkflowStepStatus.FAILED and loop_config.break_on_failure:
                    break
        
        # Mark as completed if not failed
        if step.status == SkillWorkflowStepStatus.RUNNING:
            step.status = SkillWorkflowStepStatus.COMPLETED
        step.execution_time = total_time
    
    def _get_loop_items(self, items_source: Optional[str], evaluator: ConditionEvaluator) -> Any:
        """Get items for for_each loop"""
        if not items_source:
            return []
        
        # Resolve variable reference
        import re
        step_match = re.match(r'step\.(\w+)\.(.*)', items_source)
        if step_match:
            step_id = step_match.group(1)
            path = step_match.group(2)
            
            if step_id in self._step_outputs:
                step_data = self._step_outputs[step_id]
                # Navigate through path
                parts = path.split('.')
                current = step_data
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part)
                    elif hasattr(current, part):
                        current = getattr(current, part)
                    else:
                        return []
                    if current is None:
                        return []
                return current if isinstance(current, list) else []
        
        return []
    
    def _select_dynamic_skill(
        self,
        step: SkillStep,
        workflow: SkillWorkflow,
        workflow_inputs: Dict[str, Any],
        role_id: Optional[str]
    ) -> Optional[Skill]:
        """Select a skill dynamically based on context"""
        if not step.skill_selector_config:
            return None
        
        # Get role for skill selection
        role = None
        if role_id:
            role = self.engine.role_manager.get_role(role_id)
        if not role:
            # Try to get role from workflow context or use a default
            return None
        
        # Build task description from config
        task_description = step.skill_selector_config.get("task", "")
        if not task_description:
            # Try to resolve from step inputs or workflow inputs
            task_description = step.skill_selector_config.get("task_template", "")
            if task_description:
                # Resolve variables in task description
                evaluator = ConditionEvaluator(self._step_outputs, workflow_inputs)
                task_description = evaluator._resolve_variables(task_description)
        
        # Build context for skill selection
        context = step.skill_selector_config.get("context", {})
        if isinstance(context, dict):
            # Resolve context variables
            evaluator = ConditionEvaluator(self._step_outputs, workflow_inputs)
            resolved_context = {}
            for key, value in context.items():
                if isinstance(value, str):
                    resolved_context[key] = evaluator._resolve_variables(value)
                else:
                    resolved_context[key] = value
            context = resolved_context
        
        # Add workflow context
        context["workflow_id"] = workflow.id
        context["step_id"] = step.step_id
        if self.engine.context:
            context["project_context"] = self.engine.context
        
        # Use SkillSelector to select skill
        skill_selector = SkillSelector(self.engine, self.execution_tracker)
        selected_skill = skill_selector.select_skill(
            task_description=task_description,
            role=role,
            context=context
        )
        
        return selected_skill
    
    def _execute_step(
        self,
        step: SkillStep,
        workflow: SkillWorkflow,
        workflow_inputs: Dict[str, Any],
        stage_id: Optional[str],
        role_id: Optional[str]
    ) -> None:
        """Execute a single step"""
        step.status = SkillWorkflowStepStatus.RUNNING
        start_time = time.time()
        
        try:
            # Handle dynamic skill selection
            if step.dynamic_skill:
                skill = self._select_dynamic_skill(step, workflow, workflow_inputs, role_id)
                if skill:
                    step.selected_skill_id = skill.id
                else:
                    # Try fallback skill
                    if step.fallback_skill_id:
                        skill = self.engine.role_manager.skill_library.get(step.fallback_skill_id)
                        if skill:
                            step.selected_skill_id = step.fallback_skill_id
                        else:
                            raise WorkflowError(f"Dynamic skill selection failed and fallback skill '{step.fallback_skill_id}' not found")
                    else:
                        raise WorkflowError("Dynamic skill selection failed and no fallback skill specified")
            else:
                # Use static skill_id
                if not self.engine.role_manager.skill_library:
                    raise WorkflowError("Skill library not loaded")
                
                skill = self.engine.role_manager.skill_library.get(step.skill_id)
            if not skill:
                raise WorkflowError(f"Skill '{step.skill_id}' not found")
            
            # Resolve inputs
            resolved_inputs = self._resolve_step_inputs(step, workflow_inputs)
            
            # Execute with retry
            max_retries = step.config.max_retries if step.config.retry_on_failure else 0
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = self.skill_invoker.invoke(skill, resolved_inputs)
                    
                    if result.get("success"):
                        step.result = result.get("output", {}) or {}
                        step.status = SkillWorkflowStepStatus.COMPLETED
                        
                        # Store outputs for downstream steps
                        self._step_outputs[step.step_id] = step.result
                        
                        # Record execution
                        executed_skill_id = step.selected_skill_id if step.dynamic_skill else step.skill_id
                        execution = SkillExecution(
                            skill_id=executed_skill_id,
                            input=resolved_inputs,
                            output=step.result,
                            status="success",
                            execution_time=time.time() - start_time,
                            stage_id=stage_id,
                            role_id=role_id,
                            retry_count=attempt
                        )
                        self.execution_tracker.record_execution(execution)
                        return
                    else:
                        last_error = result.get("error", "Unknown error")
                        if attempt < max_retries:
                            time.sleep(2 ** attempt)  # Exponential backoff
                        
                except Exception as e:
                    last_error = str(e)
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
            
            # All retries exhausted
            step.status = SkillWorkflowStepStatus.FAILED
            step.error = last_error
            
        except Exception as e:
            step.status = SkillWorkflowStepStatus.FAILED
            step.error = str(e)
        
        step.execution_time = time.time() - start_time
    
    def _resolve_step_inputs(
        self,
        step: SkillStep,
        workflow_inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve input variable references for a step"""
        resolved = {}
        
        for key, value in step.inputs.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_variable(value, workflow_inputs)
            else:
                resolved[key] = value
        
        return resolved
    
    def _resolve_variable(
        self,
        var_ref: str,
        workflow_inputs: Dict[str, Any]
    ) -> Any:
        """
        Resolve a variable reference.
        
        Supports:
        - {{workflow.inputs.xxx}} - Workflow input
        - {{steps.step_id.outputs.xxx}} - Step output
        """
        import re
        
        # Check for workflow inputs
        workflow_match = re.match(r'\{\{workflow\.inputs\.(\w+)\}\}', var_ref)
        if workflow_match:
            key = workflow_match.group(1)
            return workflow_inputs.get(key, var_ref)
        
        # Check for step outputs
        step_match = re.match(r'\{\{steps\.(\w+)\.outputs\.(\w+)\}\}', var_ref)
        if step_match:
            step_id = step_match.group(1)
            output_key = step_match.group(2)
            
            if step_id in self._step_outputs:
                return self._step_outputs[step_id].get(output_key, var_ref)
            return var_ref
        
        # Return as-is if not a variable reference
        return var_ref
    
    def _resolve_workflow_outputs(
        self,
        workflow: SkillWorkflow
    ) -> Dict[str, Any]:
        """Resolve final workflow output mappings"""
        resolved = {}
        
        for key, var_ref in workflow.outputs.items():
            resolved[key] = self._resolve_variable(var_ref, {})
        
        return resolved
    
    def get_workflow_status(
        self,
        workflow: SkillWorkflow
    ) -> Dict[str, Any]:
        """Get current status of a workflow execution"""
        return {
            "workflow_id": workflow.id,
            "steps": [
                {
                    "step_id": s.step_id,
                    "skill_id": s.skill_id,
                    "status": s.status.value,
                    "execution_time": s.execution_time
                }
                for s in workflow.steps
            ],
            "completed": sum(1 for s in workflow.steps 
                           if s.status == SkillWorkflowStepStatus.COMPLETED),
            "failed": sum(1 for s in workflow.steps 
                         if s.status == SkillWorkflowStepStatus.FAILED),
            "pending": sum(1 for s in workflow.steps 
                          if s.status == SkillWorkflowStepStatus.PENDING)
        }


class AgentOrchestrator:
    """
    Orchestrates Agents to execute a workflow automatically (Sequential multi-agent).
    
    This class manages the Skill Invocation Layer, which is separate from the Reasoning Layer.
    
    Architecture:
    - Reasoning Layer (Agent): Task understanding, decisions, strategy (NO skills)
    - Skill Invocation Layer (this class): Skill selection and execution
    - Execution Layer: Tool/API execution
    
    Skills are ONLY invoked through execute_skill(), never during agent reasoning.
    
    LLM Integration:
    - LLM is completely optional - core functionality works without LLM
    - Set llm_client to enable LLM features
    - Use use_llm=True in execute_stage() to explicitly enable LLM
    - Default behavior is constraint checking only (no LLM calls)
    """
    def __init__(
        self, 
        engine: 'WorkflowEngine', 
        llm_client: Optional[Any] = None,
        skill_invoker: Optional[SkillInvoker] = None
    ):
        """
        Initialize AgentOrchestrator.
        
        Args:
            engine: WorkflowEngine instance
            llm_client: Optional LLM client. If None, LLM features are disabled.
            skill_invoker: Optional custom skill invoker (defaults to PlaceholderSkillInvoker)
        """
        self.engine = engine
        self.llm_client = llm_client
        self.llm_enabled = llm_client is not None
        self.execution_log: List[Dict[str, Any]] = []
        self.execution_tracker: ExecutionTracker = ExecutionTracker()
        self.skill_selector: SkillSelector = SkillSelector(engine, self.execution_tracker)
        self.retry_handler: RetryHandler = RetryHandler(self.execution_tracker)
        
        # Skill invoker for actual skill execution
        if skill_invoker:
            self.skill_invoker = skill_invoker
        elif llm_client:
            self.skill_invoker = LLMSkillInvoker(llm_client)
        else:
            self.skill_invoker = PlaceholderSkillInvoker()
        
        # Skill workflow executor for multi-skill workflows
        self.workflow_executor = SkillWorkflowExecutor(
            engine=engine,
            skill_invoker=self.skill_invoker,
            execution_tracker=self.execution_tracker
        )

    def execute_stage(self, stage_id: str, inputs: Optional[Dict[str, Any]] = None, use_llm: bool = False) -> Dict[str, Any]:
        """
        Execute a single stage using the assigned agent.
        
        This method handles the Reasoning Layer:
        1. Creates an Agent for reasoning (task understanding, decisions)
        2. Generates prompt for LLM reasoning (NO skills involved) - only if use_llm=True
        3. Returns context for skill invocation
        
        Skills are NOT invoked here - they are invoked separately via execute_skill()
        after the agent has made decisions about what needs to be done.
        
        Args:
            stage_id: Stage ID to execute
            inputs: Optional input data
            use_llm: If True and llm_client is set, will generate LLM prompt. Default False.
        
        Returns:
            Dict with stage execution result
        """
        if use_llm and self.llm_enabled:
            return self._execute_with_llm(stage_id, inputs)
        else:
            return self.check_constraints_only(stage_id, inputs)
    
    def check_constraints_only(self, stage_id: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Check constraints and validate stage without LLM execution.
        
        This is the lightweight mode - no LLM calls, just constraint checking.
        Perfect for offline use or when you want to avoid token costs.
        
        Args:
            stage_id: Stage ID to check
            inputs: Optional input data
        
        Returns:
            Dict with constraint check result
        """
        stage = self.engine.executor._get_stage_by_id(stage_id) if self.engine.executor else None
        if not stage:
            raise WorkflowError(f"Stage '{stage_id}' not found")
            
        role = self.engine.role_manager.get_role(stage.role)
        if not role:
            raise WorkflowError(f"Role '{stage.role}' for stage '{stage_id}' not found")
        
        # Check if stage can be started
        can_start = True
        errors: List[str] = []
        if self.engine.executor:
            can_start, errors = self.engine.executor.can_transition_to(stage_id)
        
        # Create minimal agent context (no LLM prompt generation)
        agent = Agent(role, self.engine, self.skill_selector)
        goal = "Implement requirements"
        if self.engine.context and self.engine.context.specs:
            goal = self.engine.context.specs.get("global_goal", goal)
        agent.prepare(goal, inputs)
        
        result = {
            "stage": stage_id,
            "agent": agent,
            "context": agent.context,
            "status": "constraints_checked",
            "can_start": can_start,
            "errors": errors,
            "llm_used": False
        }
        
        self.execution_log.append(result)
        return result
    
    def _execute_with_llm(self, stage_id: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute stage with LLM support (requires llm_client to be set).
        
        This method generates LLM prompts and can call the LLM if needed.
        Only called when use_llm=True and llm_client is available.
        
        Args:
            stage_id: Stage ID to execute
            inputs: Optional input data
        
        Returns:
            Dict with LLM execution result
        """
        if not self.llm_enabled:
            raise WorkflowError("LLM client not available. Set llm_client in __init__ or use check_constraints_only()")
        
        stage = self.engine.executor._get_stage_by_id(stage_id) if self.engine.executor else None
        if not stage:
            raise WorkflowError(f"Stage '{stage_id}' not found")
            
        role = self.engine.role_manager.get_role(stage.role)
        if not role:
            raise WorkflowError(f"Role '{stage.role}' for stage '{stage_id}' not found")
            
        # Create agent for reasoning (Reasoning Layer - NO skills)
        agent = Agent(role, self.engine, self.skill_selector)
        goal = "Implement requirements"
        if self.engine.context and self.engine.context.specs:
            goal = self.engine.context.specs.get("global_goal", goal)
        agent.prepare(goal, inputs)
        
        # Generate prompt for reasoning (Reasoning Layer - NO skills)
        # Here we would normally call an LLM for reasoning.
        prompt = agent.generate_prompt(stage)
        
        # Note: Actual LLM call would happen here if needed
        # For now, we just return the prompt and context
        
        result = {
            "stage": stage_id,
            "agent": agent,
            "prompt": prompt,
            "context": agent.context,
            "status": "ready_for_execution",
            "llm_used": True
            # Note: Skills are invoked separately via execute_skill() after reasoning
        }
        
        self.execution_log.append(result)
        return result
    
    def execute_skill(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        stage_id: Optional[str] = None,
        role_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a skill with retry logic and tracking (Skill Invocation Layer).
        
        This is the ONLY place where skills should be invoked.
        Skills are NEVER invoked during agent reasoning (prepare, make_decision, generate_prompt).
        
        Execution flow:
        1. Agent reasoning (Reasoning Layer) - decides WHAT needs to be done
        2. Skill selection (this layer) - decides WHICH skill to use
        3. Skill execution (this layer) - executes the skill
        4. Result validation and tracking
        
        Args:
            skill_id: ID of the skill to execute
            input_data: Input data for the skill
            stage_id: Optional stage ID for tracking
            role_id: Optional role ID for tracking
            
        Returns:
            Dict with execution result
        """
        if not self.engine.role_manager.skill_library:
            raise WorkflowError("Skill library not loaded")
        
        skill = self.engine.role_manager.skill_library.get(skill_id)
        if not skill:
            raise WorkflowError(f"Skill '{skill_id}' not found")
        execution: Optional[SkillExecution] = None
        
        # Validate input schema if available
        if skill.input_schema and JSONSCHEMA_AVAILABLE:
            try:
                jsonschema.validate(input_data, skill.input_schema)
            except jsonschema.ValidationError as e:
                error_response = self.retry_handler.format_error_response(
                    e, skill, retryable=False
                )
                execution = SkillExecution(
                    skill_id=skill_id,
                    input=input_data,
                    output=None,
                    status="failed",
                    error_type=SkillErrorType.VALIDATION_ERROR.value,
                    error_message=str(e),
                    execution_time=0.0,
                    stage_id=stage_id,
                    role_id=role_id
                )
                self.execution_tracker.record_execution(execution)
                return error_response
        
        # Execute skill with retry logic
        start_time = time.time()
        last_error: Optional[Exception] = None
        
        for attempt in range(10):  # Max 10 attempts
            try:
                # Here we would normally invoke the actual skill execution
                # For now, this is a placeholder that would call LLM or tool
                result = self._invoke_skill(skill, input_data)
                
                execution_time = time.time() - start_time
                execution = SkillExecution(
                    skill_id=skill_id,
                    input=input_data,
                    output=result,
                    status="success",
                    execution_time=execution_time,
                    retry_count=attempt,
                    stage_id=stage_id,
                    role_id=role_id
                )
                self.execution_tracker.record_execution(execution)
                
                return {
                    "success": True,
                    "output": result,
                    "execution_time": execution_time,
                    "retry_count": attempt
                }
                
            except Exception as e:
                last_error = e
                execution_time = time.time() - start_time
                
                # Create execution record for this attempt
                execution = SkillExecution(
                    skill_id=skill_id,
                    input=input_data,
                    output=None,
                    status="failed" if attempt == 0 else "retried",
                    error_type=self.retry_handler._classify_error(e).value,
                    error_message=str(e),
                    execution_time=execution_time,
                    retry_count=attempt,
                    stage_id=stage_id,
                    role_id=role_id
                )
                self.execution_tracker.record_execution(execution)
                
                # Check if should retry
                if not self.retry_handler.should_retry(e, skill, execution):
                    break
                
                # Get retry delay and wait
                retry_config = self.retry_handler.handle_retry(skill_id, input_data, e, skill)
                time.sleep(retry_config['delay'])
        
        # All retries exhausted
        error_obj: Exception = last_error if last_error else Exception("Unknown error")
        error_response = self.retry_handler.format_error_response(
            error_obj, skill, retryable=False
        )
        return error_response
    
    def _invoke_skill(self, skill: Skill, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke skill using the configured skill invoker.
        
        Uses the skill_invoker set during initialization:
        - LLMSkillInvoker if llm_client was provided
        - PlaceholderSkillInvoker by default
        - Custom invoker if provided
        
        Args:
            skill: Skill definition to execute
            input_data: Input data for the skill
            
        Returns:
            Dict with execution result
        """
        result = cast(Dict[str, Any], self.skill_invoker.invoke(skill, input_data))
        
        if result.get("success"):
            output = result.get("output", {}) or {}
            if isinstance(output, dict):
                return cast(Dict[str, Any], output)
            return {"output": output}
        else:
            raise WorkflowError(
                f"Skill execution failed: {result.get('error', 'Unknown error')}",
                context={"skill_id": skill.id, "input": input_data}
            )

    def complete_stage(self, stage_id: str) -> Dict[str, Any]:
        """Validate and complete a stage"""
        passed, errors = self.engine.complete_stage(stage_id)
        return {
            "stage": stage_id,
            "quality_gates_passed": passed,
            "errors": errors,
            "result": self.execution_log[-1] if self.execution_log else None
        }

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of automated execution"""
        return {
            "total_stages_executed": len(self.execution_log),
            "agents_used": list(set(log["agent"].role.id for log in self.execution_log)),
            "log": self.execution_log
        }
    
    # ========================================================================
    # Skill Workflow Methods - 多技能工作流执行
    # ========================================================================
    
    def execute_skill_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        stage_id: Optional[str] = None,
        role_id: Optional[str] = None
    ) -> SkillWorkflowExecution:
        """
        Execute a skill workflow (multi-skill pipeline).
        
        This is the main entry point for executing skill workflows that combine
        multiple skills in a dependency-based execution graph.
        
        Args:
            workflow_id: ID of the skill workflow to execute
            inputs: Initial inputs for the workflow
            stage_id: Optional stage context for tracking
            role_id: Optional role context for tracking
            
        Returns:
            SkillWorkflowExecution with complete execution details
            
        Example:
            >>> result = orchestrator.execute_skill_workflow(
            ...     "feature_delivery",
            ...     {"goal": "Build user auth", "context": {"framework": "FastAPI"}}
            ... )
            >>> print(result.status)  # "completed" or "failed"
            >>> print(result.outputs)  # Final workflow outputs
        """
        return self.workflow_executor.execute_workflow(
            workflow_id=workflow_id,
            inputs=inputs,
            stage_id=stage_id,
            role_id=role_id
        )
    
    def list_skill_workflows(self) -> List[Dict[str, Any]]:
        """
        List all available skill workflows.
        
        Returns:
            List of workflow summaries with id, name, description, and step count
        """
        workflows = []
        for wf_id, wf in self.engine.role_manager.skill_workflows.items():
            workflows.append({
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "steps": len(wf.steps),
                "trigger": {
                    "stage_id": wf.trigger.stage_id,
                    "condition": wf.trigger.condition
                }
            })
        return workflows
    
    def get_skill_workflow(self, workflow_id: str) -> Optional[SkillWorkflow]:
        """
        Get a skill workflow by ID.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            SkillWorkflow or None if not found
        """
        return self.engine.role_manager.skill_workflows.get(workflow_id)
    
    def get_workflow_details(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a skill workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Dict with workflow details including steps, dependencies, and config
        """
        workflow = self.get_skill_workflow(workflow_id)
        if not workflow:
            return None
        
        return {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "trigger": {
                "stage_id": workflow.trigger.stage_id,
                "condition": workflow.trigger.condition,
                "event_type": workflow.trigger.event_type
            },
            "config": {
                "max_parallel": workflow.config.max_parallel,
                "fail_fast": workflow.config.fail_fast,
                "retry_failed_steps": workflow.config.retry_failed_steps,
                "timeout": workflow.config.timeout
            },
            "steps": [
                {
                    "step_id": s.step_id,
                    "skill_id": s.skill_id,
                    "name": s.name,
                    "order": s.order,
                    "depends_on": s.depends_on,
                    "inputs": s.inputs,
                    "outputs": s.outputs
                }
                for s in workflow.steps
            ],
            "outputs": workflow.outputs,
            "execution_order": [s.step_id for s in workflow.topological_sort()]
        }
    
    def execute_stage_with_workflows(
        self,
        stage_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        auto_execute_workflows: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a stage and optionally auto-trigger associated skill workflows.
        
        This combines stage execution with automatic skill workflow execution
        for workflows that have auto-trigger configured for this stage.
        
        Args:
            stage_id: Stage ID to execute
            inputs: Optional input data
            auto_execute_workflows: If True, execute workflows with auto-trigger
            
        Returns:
            Dict with stage and workflow execution results
        """
        # Execute stage
        stage_result = self.execute_stage(stage_id, inputs)
        
        # Get stage and agent objects
        stage = self.engine.executor._get_stage_by_id(stage_id) if self.engine.executor else None
        agent = stage_result.get("agent")
        
        workflow_results = []
        stage_summary = []  # Collect stage conclusions
        
        if auto_execute_workflows:
            # Find workflows that auto-trigger on this stage
            auto_workflows = self.engine.role_manager.get_workflows_for_stage(stage_id)
            
            for workflow in auto_workflows:
                try:
                    wf_result = self.workflow_executor.execute_workflow(
                        workflow_id=workflow.id,
                        inputs=inputs or {},
                        stage_id=stage_id,
                        role_id=stage_result.get("agent", {}).role.id if stage_result.get("agent") else None
                    )
                    workflow_results.append({
                        "workflow_id": workflow.id,
                        "status": wf_result.status,
                        "outputs": wf_result.outputs,
                        "errors": wf_result.errors
                    })
                    
                    # Collect workflow execution results and format as readable text
                    if wf_result.outputs:
                        summary = self._format_workflow_summary(
                            workflow_id=workflow.id,
                            outputs=wf_result.outputs,
                            stage=stage
                        )
                        if summary:
                            stage_summary.append(summary)
                            
                except Exception as e:
                    workflow_results.append({
                        "workflow_id": workflow.id,
                        "status": "error",
                        "error": str(e)
                    })
        
        # Generate stage output files
        if agent and stage:
            try:
                self._generate_stage_output_files(
                    stage=stage,
                    agent=agent,
                    workflow_results=workflow_results
                )
            except Exception as e:
                # Don't fail the entire workflow if file generation fails
                warnings.warn(f"Failed to generate stage output files: {e}")
        
        # Generate conversation summary
        conversation_summary = self._generate_conversation_summary(
            stage=stage,
            agent=agent,
            workflow_results=workflow_results,
            stage_summary=stage_summary
        )
        
        return {
            **stage_result,
            "skill_workflows": workflow_results,
            "conversation_summary": conversation_summary,
            "stage_summary": stage_summary
        }
    
    def _generate_stage_output_files(
        self,
        stage: Stage,
        agent: "Agent",
        workflow_results: List[Dict[str, Any]]
    ) -> None:
        """
        Generate output files based on stage.outputs configuration.
        
        Args:
            stage: Stage definition with outputs configuration
            agent: Agent instance for producing outputs
            workflow_results: List of workflow execution results
        """
        if not stage.outputs:
            return
        
        for output in stage.outputs:
            # Only generate document and report type outputs
            if output.type not in ("document", "report"):
                continue
            
            # Check if file already exists (skip if optional and exists)
            output_path = self.engine.workspace_path / ".workflow" / "temp" / output.name
            if output_path.exists() and not output.required:
                continue  # Optional output already exists, skip
            
            # Extract or generate content
            content = self._extract_or_generate_content(
                output=output,
                workflow_results=workflow_results,
                agent=agent,
                stage=stage
            )
            
            # For required outputs, ensure content is always generated (Lovable workflow pattern)
            if output.required and not content:
                # Generate basic template for required outputs
                content = self._generate_basic_template(output, stage)
                if not content:
                    # Fallback: create minimal content
                    content = f"# {stage.name}\n\n*此文档由工作流系统自动生成，待完善*\n"
            
            # Call agent.produce_output() to save file
            if content:
                try:
                    agent.produce_output(
                        name=output.name,
                        content=content,
                        output_type=output.type
                    )
                except Exception as e:
                    if output.required:
                        # For required outputs, raise error instead of warning
                        raise WorkflowError(
                            f"Failed to produce required output file {output.name}: {e}",
                            context={"output": output.name, "stage": stage.id}
                        )
                    else:
                        warnings.warn(f"Failed to produce output file {output.name}: {e}")
    
    def _extract_or_generate_content(
        self,
        output: Output,
        workflow_results: List[Dict[str, Any]],
        agent: "Agent",
        stage: Stage
    ) -> Optional[str]:
        """
        Extract content from skill execution results or generate content.
        
        Args:
            output: Output definition
            workflow_results: List of workflow execution results
            agent: Agent instance
            stage: Stage definition
            
        Returns:
            Content string or None if not found
        """
        # Priority 1: Extract from workflow results
        for wf_result in workflow_results:
            if wf_result.get("outputs"):
                outputs = wf_result["outputs"]
                # Try common content keys
                for key in ["content", "document", "summary", "markdown", "text", output.name]:
                    if key in outputs:
                        value = outputs[key]
                        if isinstance(value, str):
                            return value
                        elif isinstance(value, dict):
                            # Try nested content keys
                            for nested_key in ["content", "document", "summary", "text", "body"]:
                                if nested_key in value:
                                    nested_value = value[nested_key]
                                    if isinstance(nested_value, str):
                                        return nested_value
                            # If dict has string values, format as markdown
                            return f"```json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```"
        
        # Priority 2: Check agent context outputs
        if agent and agent.context and agent.context.outputs:
            if output.name in agent.context.outputs:
                output_path = Path(agent.context.outputs[output.name])
                if output_path.exists():
                    return output_path.read_text(encoding='utf-8')
        
        # Priority 3: Generate basic template if required
        if output.required:
            # Generate a basic template based on stage and output type
            template = self._generate_basic_template(output, stage)
            return template
        
        return None
    
    def _generate_basic_template(
        self,
        output: Output,
        stage: Stage
    ) -> str:
        """
        Generate a basic template for required outputs.
        
        Args:
            output: Output definition
            stage: Stage definition
            
        Returns:
            Basic template content
        """
        lines = [f"# {stage.name}"]
        lines.append("")
        lines.append(f"**阶段**: {stage.name}")
        if stage.goal_template:
            lines.append(f"**目标**: {stage.goal_template}")
        lines.append("")
        lines.append("## 概述")
        lines.append("")
        lines.append("（待完善）")
        lines.append("")
        lines.append("---")
        lines.append(f"*此文档由工作流系统自动生成*")
        return "\n".join(lines)
    
    def _format_workflow_summary(
        self,
        workflow_id: str,
        outputs: Dict[str, Any],
        stage: Optional[Stage]
    ) -> Optional[str]:
        """
        Format workflow outputs as readable markdown text.
        
        Args:
            workflow_id: Workflow ID
            outputs: Workflow outputs dictionary
            stage: Optional stage definition
            
        Returns:
            Formatted markdown text or None
        """
        if not outputs:
            return None
        
        parts = []
        
        # Try to extract key information
        for key, value in outputs.items():
            if isinstance(value, dict):
                # If dict, try to extract document content
                if "content" in value:
                    parts.append(f"### {key}\n{value['content']}")
                elif "document" in value:
                    parts.append(f"### {key}\n{value['document']}")
                elif "summary" in value:
                    parts.append(f"### {key}\n{value['summary']}")
                elif "markdown" in value:
                    parts.append(f"### {key}\n{value['markdown']}")
                else:
                    # Format entire dict
                    parts.append(f"### {key}\n```json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```")
            elif isinstance(value, str):
                parts.append(f"### {key}\n{value}")
            else:
                parts.append(f"### {key}\n{str(value)}")
        
        return "\n\n".join(parts) if parts else None
    
    def _generate_conversation_summary(
        self,
        stage: Optional[Stage],
        agent: Optional["Agent"],
        workflow_results: List[Dict[str, Any]],
        stage_summary: List[str]
    ) -> str:
        """
        Generate conversation summary for stage execution.
        
        Args:
            stage: Optional stage definition
            agent: Optional agent instance
            workflow_results: List of workflow execution results
            stage_summary: List of formatted workflow summaries
            
        Returns:
            Formatted markdown summary
        """
        if not stage:
            return ""
        
        parts = []
        
        # Stage title
        parts.append(f"## {stage.name}")
        
        # Stage goal
        if stage.goal_template:
            parts.append(f"\n**目标**: {stage.goal_template}")
        
        # Skill execution results summary
        if stage_summary:
            parts.append("\n### 执行结果\n")
            parts.extend(stage_summary)
        
        # If no documents generated, create an execution summary
        if not stage_summary and workflow_results:
            parts.append("\n### 执行摘要\n")
            for wf_result in workflow_results:
                if wf_result.get("status") == "completed":
                    parts.append(f"- ✅ 工作流 `{wf_result.get('workflow_id')}` 执行成功")
                    if wf_result.get("outputs"):
                        parts.append(f"  输出: {len(wf_result['outputs'])} 项")
                elif wf_result.get("status") == "failed":
                    parts.append(f"- ❌ 工作流 `{wf_result.get('workflow_id')}` 执行失败")
                    if wf_result.get("error"):
                        parts.append(f"  错误: {wf_result['error']}")
                elif wf_result.get("status") == "error":
                    parts.append(f"- ❌ 工作流 `{wf_result.get('workflow_id')}` 执行出错")
                    if wf_result.get("error"):
                        parts.append(f"  错误: {wf_result['error']}")
        
        # Agent decisions (if any)
        if agent and agent.context and agent.context.decisions:
            parts.append("\n### 关键决策\n")
            for decision in agent.context.decisions:
                parts.append(f"- {decision}")
        
        return "\n".join(parts)


class RoleExecutor:
    """
    简化的角色执行器 - 直接执行角色和技能，无需workflow阶段。
    
    适用于IDE环境（如Cursor），用户指定角色和需求，角色使用skills来处理。
    
    架构：
    - 用户指定角色和需求
    - 角色根据需求选择合适的skills
    - 执行skills并返回结果
    """
    
    def __init__(
        self,
        engine: 'WorkflowEngine',
        llm_client: Optional[Any] = None,
        skill_invoker: Optional[SkillInvoker] = None
    ):
        """
        初始化RoleExecutor。
        
        Args:
            engine: WorkflowEngine实例（用于访问角色和技能库）
            llm_client: 可选的LLM客户端
            skill_invoker: 可选的技能调用器
        """
        self.engine = engine
        self.llm_client = llm_client
        self.skill_selector = SkillSelector(engine)
        self.execution_tracker = ExecutionTracker()
        
        # 使用AgentOrchestrator的技能执行能力
        self.orchestrator = AgentOrchestrator(
            engine=engine,
            llm_client=llm_client,
            skill_invoker=skill_invoker
        )
    
    def execute_role(
        self,
        role_id: str,
        requirement: str,
        inputs: Optional[Dict[str, Any]] = None,
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        执行角色处理需求。
        
        Args:
            role_id: 角色ID
            requirement: 用户需求描述
            inputs: 可选的输入数据
            use_llm: 是否使用LLM进行推理（需要llm_client）
            
        Returns:
            包含执行结果的字典
        """
        # 1. 获取角色
        role = self.engine.role_manager.get_role(role_id)
        if not role:
            raise WorkflowError(f"Role '{role_id}' not found")
        
        # 2. 创建Agent
        agent = Agent(role, self.engine, self.skill_selector)
        agent.prepare(requirement, inputs or {})
        
        # 3. 构建完整上下文
        full_context = self._build_context(role, requirement, agent.context, inputs or {})
        
        # 4. 根据需求选择合适的技能
        selected_skills = self._select_skills_for_requirement(role, requirement, full_context)
        
        # 4. 执行技能
        skill_results = []
        for skill_id in selected_skills:
            try:
                skill_input = self._prepare_skill_input(requirement, inputs or {}, agent.context)
                result = self.orchestrator.execute_skill(
                    skill_id=skill_id,
                    input_data=skill_input,
                    role_id=role_id
                )
                skill_results.append({
                    "skill_id": skill_id,
                    "result": result
                })
            except Exception as e:
                skill_results.append({
                    "skill_id": skill_id,
                    "error": str(e)
                })
        
        # 5. 生成最终响应
        final_response = self._generate_response(
            role=role,
            requirement=requirement,
            skill_results=skill_results,
            agent=agent,
            use_llm=use_llm
        )
        
        return {
            "role_id": role_id,
            "requirement": requirement,
            "skills_executed": [r["skill_id"] for r in skill_results],
            "skill_results": skill_results,
            "response": final_response,
            "agent_context": agent.context
        }
    
    def _build_context(
        self,
        role: Role,
        requirement: str,
        agent_context: Optional[AgentContext],
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建完整的上下文信息用于技能选择"""
        context = {
            "requirement": requirement,
            "role_id": role.id,
            "inputs": inputs
        }
        
        # 添加项目上下文
        if agent_context and agent_context.project_context:
            pc = agent_context.project_context
            context["project_context"] = pc
            
            # 提取项目类型和技术栈
            if pc.specs:
                project_type = pc.specs.get("project_type", "")
                if project_type:
                    context["project_type"] = project_type
            
            # 从路径推断技术栈
            tech_stack = []
            if pc.paths:
                if "src" in pc.paths:
                    tech_stack.append("python")
                if "requirements.txt" in str(pc.root_path):
                    tech_stack.append("python")
            if tech_stack:
                context["tech_stack"] = tech_stack
        
        # 添加当前阶段（如果有）
        if self.engine.executor and self.engine.executor.state:
            current_stage = self.engine.executor.state.current_stage
            if current_stage:
                context["current_stage"] = current_stage
        
        # 添加历史技能执行记录
        if self.execution_tracker:
            previous_skills = []
            # Get unique skill IDs from execution history
            unique_skill_ids = set(e.skill_id for e in self.execution_tracker.executions)
            for skill_id in unique_skill_ids:
                history = self.execution_tracker.get_skill_history(skill_id)
                if any(e.status == "success" for e in history):
                    previous_skills.append(skill_id)
            if previous_skills:
                context["previous_skills"] = previous_skills
        
        return context
    
    def _select_skills_for_requirement(
        self,
        role: Role,
        requirement: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        根据需求和角色选择合适的技能。
        
        优先使用角色required_skills中定义的技能。
        """
        selected = []
        context = context or {}
        
        # 优先使用角色required_skills中定义的技能
        if role.required_skills:
            for skill_req in role.required_skills:
                if skill_req.skill_id not in selected:
                    # 检查技能是否存在
                    if self.engine.role_manager.skill_library:
                        skill = self.engine.role_manager.skill_library.get(skill_req.skill_id)
                        if skill:
                            selected.append(skill_req.skill_id)
        
        # 如果没有required_skills或没有找到技能，使用SkillSelector自动选择
        if not selected:
            skill = self.skill_selector.select_skill(
                task_description=requirement,
                role=role,
                context=context
            )
            if skill and skill.id not in selected:
                selected.append(skill.id)
        
        return selected
    
    def _prepare_skill_input(
        self,
        requirement: str,
        inputs: Dict[str, Any],
        context: Optional[AgentContext]
    ) -> Dict[str, Any]:
        """准备技能输入数据"""
        skill_input = {
            "requirement": requirement,
            **inputs
        }
        
        if context:
            skill_input["workspace_path"] = str(context.workspace_path)
            if context.project_context:
                skill_input["project_context"] = context.project_context.to_dict()
        
        return skill_input
    
    def _generate_response(
        self,
        role: Role,
        requirement: str,
        skill_results: List[Dict[str, Any]],
        agent: Agent,
        use_llm: bool
    ) -> str:
        """
        生成最终响应。
        
        如果use_llm=True且有llm_client，使用LLM生成响应。
        否则，简单汇总技能执行结果。
        """
        if use_llm and self.llm_client:
            # 使用LLM生成响应
            prompt = self._build_response_prompt(role, requirement, skill_results)
            try:
                if hasattr(self.llm_client, 'complete'):
                    response = self.llm_client.complete(prompt)
                elif hasattr(self.llm_client, 'chat'):
                    response = self.llm_client.chat([{"role": "user", "content": prompt}])
                elif callable(self.llm_client):
                    response = self.llm_client(prompt)
                else:
                    response = self._format_simple_response(skill_results)
                return str(response)
            except Exception as e:
                # LLM调用失败，回退到简单响应
                return self._format_simple_response(skill_results)
        else:
            # 简单汇总响应
            return self._format_simple_response(skill_results)
    
    def _build_response_prompt(
        self,
        role: Role,
        requirement: str,
        skill_results: List[Dict[str, Any]]
    ) -> str:
        """构建LLM响应提示"""
        prompt_parts = [
            f"You are acting as a {role.name}.",
            f"Description: {role.description}\n",
            f"User Requirement: {requirement}\n",
            "Skill Execution Results:"
        ]
        
        for i, result in enumerate(skill_results, 1):
            prompt_parts.append(f"\n{i}. Skill: {result['skill_id']}")
            if "result" in result:
                prompt_parts.append(f"   Result: {json.dumps(result['result'], indent=2)}")
            if "error" in result:
                prompt_parts.append(f"   Error: {result['error']}")
        
        prompt_parts.append("\nBased on the skill execution results above, provide a comprehensive response to the user's requirement.")
        if role.instruction_template:
            prompt_parts.append(f"\nRole Instructions:\n{role.instruction_template}")
        
        return "\n".join(prompt_parts)
    
    def _format_simple_response(self, skill_results: List[Dict[str, Any]]) -> str:
        """格式化简单响应（不使用LLM）"""
        response_parts = ["技能执行结果汇总：\n"]
        
        for i, result in enumerate(skill_results, 1):
            response_parts.append(f"{i}. 技能: {result['skill_id']}")
            if "result" in result:
                if result['result'].get('success'):
                    response_parts.append(f"   ✅ 执行成功")
                    if result['result'].get('output'):
                        output = result['result']['output']
                        if isinstance(output, dict):
                            response_parts.append(f"   输出: {json.dumps(output, indent=2, ensure_ascii=False)}")
                        else:
                            response_parts.append(f"   输出: {output}")
                else:
                    response_parts.append(f"   ❌ 执行失败")
            if "error" in result:
                response_parts.append(f"   ❌ 错误: {result['error']}")
            response_parts.append("")
        
        return "\n".join(response_parts)


class SkillBenchmark:
    """Benchmark system for evaluating skill performance"""
    
    def __init__(self, engine: 'WorkflowEngine', orchestrator: Optional[AgentOrchestrator] = None):
        self.engine = engine
        self.orchestrator = orchestrator or AgentOrchestrator(engine)
    
    def benchmark_skill(
        self,
        skill_id: str,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Benchmark a single skill with test cases"""
        if not self.engine.role_manager.skill_library:
            raise WorkflowError("Skill library not loaded")
        
        skill = self.engine.role_manager.skill_library.get(skill_id)
        if not skill:
            raise WorkflowError(f"Skill '{skill_id}' not found")
        
        results = []
        total_time = 0.0
        successes = 0
        
        for test_case in test_cases:
            test_name = test_case.get('name', 'unnamed_test')
            input_data = test_case.get('input', {})
            expected_output = test_case.get('expected_output', {})
            
            start_time = time.time()
            try:
                result = self.orchestrator.execute_skill(skill_id, input_data)
                execution_time = time.time() - start_time
                total_time += execution_time
                
                success = result.get('success', False)
                if success:
                    successes += 1
                
                # Validate output if expected_output provided
                output_valid = True
                if expected_output and result.get('output'):
                    output_valid = self._validate_output(result['output'], expected_output)
                
                results.append({
                    "test_name": test_name,
                    "success": success and output_valid,
                    "execution_time": execution_time,
                    "result": result,
                    "output_valid": output_valid
                })
            except Exception as e:
                execution_time = time.time() - start_time
                total_time += execution_time
                results.append({
                    "test_name": test_name,
                    "success": False,
                    "execution_time": execution_time,
                    "error": str(e)
                })
        
        return {
            "skill_id": skill_id,
            "total_tests": len(test_cases),
            "successful_tests": successes,
            "success_rate": successes / len(test_cases) if test_cases else 0.0,
            "avg_execution_time": total_time / len(test_cases) if test_cases else 0.0,
            "total_execution_time": total_time,
            "results": results
        }
    
    def benchmark_skill_pair(
        self,
        skill_a_id: str,
        skill_b_id: str,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Benchmark two skills in sequence (e.g., generate -> review)"""
        results_a = self.benchmark_skill(skill_a_id, test_cases)
        results_b = self.benchmark_skill(skill_b_id, test_cases)
        
        # Check if skills complement each other
        complementary = True
        if results_a['success_rate'] > 0.8 and results_b['success_rate'] > 0.8:
            # Both skills perform well individually
            complementary = True
        
        return {
            "skill_a": results_a,
            "skill_b": results_b,
            "complementary": complementary,
            "combined_success_rate": (results_a['success_rate'] + results_b['success_rate']) / 2
        }
    
    def compare_skills(
        self,
        skill_ids: List[str],
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare multiple skills on the same test cases"""
        comparisons = {}
        
        for skill_id in skill_ids:
            comparisons[skill_id] = self.benchmark_skill(skill_id, test_cases)
        
        # Rank skills by success rate
        ranked = sorted(
            comparisons.items(),
            key=lambda x: x[1]['success_rate'],
            reverse=True
        )
        
        return {
            "comparisons": comparisons,
            "ranked": [{"skill_id": skill_id, **stats} for skill_id, stats in ranked],
            "best_skill": ranked[0][0] if ranked else None
        }
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate a human-readable benchmark report"""
        lines = []
        lines.append("=" * 60)
        lines.append("Skill Benchmark Report")
        lines.append("=" * 60)
        lines.append("")
        
        if 'skill_id' in results:
            # Single skill benchmark
            lines.append(f"Skill: {results['skill_id']}")
            lines.append(f"Total Tests: {results['total_tests']}")
            lines.append(f"Successful: {results['successful_tests']}")
            lines.append(f"Success Rate: {results['success_rate']:.2%}")
            lines.append(f"Avg Execution Time: {results['avg_execution_time']:.2f}s")
            lines.append("")
            lines.append("Test Results:")
            for result in results['results']:
                status = "✅" if result['success'] else "❌"
                lines.append(f"  {status} {result['test_name']}: {result.get('execution_time', 0):.2f}s")
        
        elif 'comparisons' in results:
            # Comparison report
            lines.append("Skill Comparison")
            lines.append("")
            for skill_id, stats in results['comparisons'].items():
                lines.append(f"{skill_id}:")
                lines.append(f"  Success Rate: {stats['success_rate']:.2%}")
                lines.append(f"  Avg Time: {stats['avg_execution_time']:.2f}s")
                lines.append("")
            lines.append(f"Best Skill: {results['best_skill']}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _validate_output(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> bool:
        """Validate actual output against expected output"""
        for key, expected_value in expected.items():
            if key not in actual:
                return False
            # Simple equality check - could be enhanced with schema validation
            if actual[key] != expected_value:
                return False
        return True
