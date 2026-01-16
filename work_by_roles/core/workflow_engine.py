"""
Workflow engine for managing workflow execution.
Following Single Responsibility Principle - handles workflow management only.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .exceptions import ValidationError, WorkflowError
from .enums import StageStatus
from .models import (
    Workflow, Stage, QualityGate, Output, ProjectContext
)
from .schema_loader import SchemaLoader
from .config_loader import ConfigLoader
from .role_manager import RoleManager
from .workflow_executor import WorkflowExecutor
from .state_storage import StateStorage, FileStateStorage
from .quality_gates import QualityGateSystem

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
    
        # Checkpoint manager (lazy initialization)
        self._checkpoint_manager: Optional[Any] = None
        self.auto_checkpoint = False  # Auto-create checkpoints on stage transitions
    
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
    
    @property
    def checkpoint_manager(self) -> Any:
        """Lazy initialization of checkpoint manager"""
        if self._checkpoint_manager is None:
            from .checkpoint_manager import CheckpointManager
            self._checkpoint_manager = CheckpointManager(self.workspace_path)
        return self._checkpoint_manager

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
            
            # Auto-create checkpoint if enabled
            if self.auto_checkpoint:
                self._create_checkpoint_auto(stage_id, f"Stage complete: {stage_id}")
            
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


# ExecutionTracker, SkillSelector, RetryHandler, and ConditionEvaluator have been moved to separate modules
# They are imported above and re-exported for backward compatibility.


