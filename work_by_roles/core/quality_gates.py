"""
Quality gate system for evaluating workflow stage quality gates.
Following Single Responsibility Principle - handles quality gate evaluation only.
"""

import subprocess
from typing import Dict, List, Callable, Any, Tuple, Optional
from pathlib import Path

from .exceptions import ValidationError
from .models import QualityGate, Stage
from .role_manager import RoleManager
from .schema_loader import SchemaLoader


class QualityGateSystem:
    """Manages quality gate evaluation with pluggable validators"""
    
    # Type alias for validator function signature
    ValidatorFunc = Callable[[Any, Stage, Path], Tuple[bool, List[str]]]
    
    def __init__(self, role_manager: RoleManager, workflow_id: Optional[str] = None):
        self.role_manager = role_manager
        self.workflow_id = workflow_id
        self._validators: Dict[str, QualityGateSystem.ValidatorFunc] = {}
        self._register_default_validators()
    
    def register_validator(self, gate_type: str, validator: ValidatorFunc) -> None:
        """
        Register a custom validator function.
        
        Args:
            gate_type: The quality gate type identifier (e.g., "code_quality")
            validator: A function with signature (gate: QualityGate, stage: Stage, workspace_path: Path) -> (bool, List[str])
        
        Example:
            def my_validator(gate, stage, workspace_path):
                # Custom validation logic
                return True, []
            
            system.register_validator("my_custom_type", my_validator)
        """
        if not callable(validator):
            raise ValidationError(f"Validator for '{gate_type}' must be callable")
        self._validators[gate_type] = validator
    
    def _register_default_validators(self) -> None:
        """Register all built-in validators"""
        try:
            from ..validators.implementations import LinterValidator, TestValidator
            
            self._validators["schema_validation"] = self._validate_schemas
            self._validators["completeness"] = self._validate_completeness
            self._validators["document_validation"] = self._validate_document
            self._validators["end_to_end"] = self._validate_e2e
            self._validators["documentation"] = self._validate_documentation
            self._validators["spec_compliance"] = self._validate_spec_compliance
            self._validators["content_validator"] = self._validate_content
            
            # New class-based validators
            linter = LinterValidator()
            tester = TestValidator()
            self._validators["code_quality"] = linter.validate
            self._validators["functionality"] = tester.validate
        except ImportError:
            # Fallback if validators module not available
            self._validators["schema_validation"] = self._validate_schemas
            self._validators["completeness"] = self._validate_completeness
            self._validators["document_validation"] = self._validate_document
            self._validators["end_to_end"] = self._validate_e2e
            self._validators["documentation"] = self._validate_documentation
            self._validators["spec_compliance"] = self._validate_spec_compliance
            self._validators["content_validator"] = self._validate_content
    
    def evaluate_gate(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """
        Evaluate a quality gate using registered validators.
        
        The validator is selected by:
        1. gate.validator field (if specified and exists)
        2. gate.type field (fallback)
        
        Args:
            gate: The quality gate to evaluate
            stage: The workflow stage being validated
            workspace_path: Path to the workspace root
            
        Returns:
            Tuple of (passed: bool, errors: List[str])
        """
        # Try validator field first, then fall back to type
        validator_key = None
        validator = None
        
        if gate.validator:
            validator = self._validators.get(gate.validator)
            if validator:
                validator_key = gate.validator
        
        # Fall back to type if validator field not found or not specified
        if validator is None:
            validator_key = gate.type
            validator = self._validators.get(gate.type)
        
        if validator is None:
            available = ', '.join(self._validators.keys())
            return False, [f"Unknown quality gate validator: '{validator_key}'. Available: {available}"]
        
        try:
            return validator(gate, stage, workspace_path)
        except Exception as e:
            return False, [f"Validator '{validator_key}' raised exception: {str(e)}"]
    
    def _validate_schemas(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """Validate schema files"""
        errors = []
        # Basic validation: check if schema files exist and are parseable
        schema_files = list(workspace_path.glob("*.yaml")) + list(workspace_path.glob("*.yml"))
        for schema_file in schema_files:
            if "schema" in schema_file.name.lower():
                try:
                    SchemaLoader.load_schema(schema_file)
                except Exception as e:
                    errors.append(f"Schema validation failed for {schema_file.name}: {e}")
        return len(errors) == 0, errors
    
    def _get_output_path(self, output_name: str, output_type: str, stage_id: str, workspace_path: Path) -> Path:
        """
        Get the output path for a file based on type, workflow_id, and stage_id.
        
        Args:
            output_name: Output file name
            output_type: Type of output ("document", "report", "code", etc.)
            stage_id: Stage ID
            workspace_path: Workspace root path
            
        Returns:
            Path object for the output file
        """
        # Get workflow_id
        workflow_id = self.workflow_id or "default"
        
        # Determine path based on type
        if output_type in ("document", "report"):
            # All document and report types go to .workflow/outputs/{workflow_id}/{stage_id}/
            path = workspace_path / ".workflow" / "outputs" / workflow_id / stage_id / output_name
        else:
            # Code, tests, and other types go to workspace root
            path = workspace_path / output_name
        
        return path
    
    def _validate_completeness(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """Validate completeness of stage outputs"""
        errors = []
        for output in stage.outputs:
            # Get output path using unified path calculation
            output_path = self._get_output_path(output.name, output.type, stage.id, workspace_path)
            
            if output.required and not output_path.exists():
                errors.append(f"Required output '{output.name}' not found")
        return len(errors) == 0, errors
    
    def _validate_code_quality(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """Validate code quality (placeholder - would run linters)"""
        # In a real implementation, this would run ruff, mypy, etc.
        return True, []
    
    def _validate_functionality(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """Validate functionality (placeholder - would run tests)"""
        # In a real implementation, this would run pytest
        return True, []
    
    def _validate_document(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """Validate document structure"""
        errors = []
        for output in stage.outputs:
            if output.type == "document":
                # Get document path using unified path calculation
                doc_path = self._get_output_path(output.name, output.type, stage.id, workspace_path)
                if doc_path.exists():
                    content = doc_path.read_text(encoding='utf-8')
                    for criterion in gate.criteria:
                        if criterion == "must_contain_project_overview" and "project" not in content.lower():
                            errors.append(f"Document {output.name} missing project overview")
                        elif criterion == "must_contain_success_criteria" and "success" not in content.lower():
                            errors.append(f"Document {output.name} missing success criteria")
        return len(errors) == 0, errors
    
    def _validate_e2e(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """Validate end-to-end workflow"""
        # Placeholder for E2E tests
        return True, []
    
    def _validate_documentation(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """Validate documentation completeness"""
        errors = []
        readme_path = workspace_path / "README.md"
        if not readme_path.exists():
            errors.append("README.md not found")
        return len(errors) == 0, errors

    def _validate_content(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """Validate content-based criteria (e.g., skill updates)"""
        errors = []
        for criterion in gate.criteria:
            if criterion == "skills_updated_with_lessons":
                changed_skills = self._find_changed_skill_files(workspace_path)
                if not changed_skills:
                    errors.append("No Skill.md changes detected for skills_updated_with_lessons")
        return len(errors) == 0, errors

    def _find_changed_skill_files(self, workspace_path: Path) -> List[str]:
        """Find Skill.md files changed in the working tree (git-based)."""
        if not (workspace_path / ".git").exists():
            return []
        try:
            subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                check=True,
            )
            diff_result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                check=True,
            )
            candidates = diff_result.stdout.splitlines()
        except subprocess.CalledProcessError:
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
            )
            candidates = []
            for line in status_result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                # format: XY path
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    candidates.append(parts[1])
        return [path for path in candidates if path.endswith("Skill.md")]
    
    def _validate_spec_compliance(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """Validate implementation compliance with spec files"""
        errors = []
        
        # Find spec files in project
        spec_patterns = ["*.spec.md", "*.spec.yaml", "*.spec.yml", "openapi.yaml", "swagger.json"]
        spec_files = []
        for pattern in spec_patterns:
            spec_files.extend(list(workspace_path.glob(f"**/{pattern}")))
        
        if not spec_files:
            # If spec_file_exists is required, this is an error
            if "spec_file_exists" in gate.criteria:
                errors.append("No spec files found (expected *.spec.md, *.spec.yaml, openapi.yaml, etc.)")
            return len(errors) == 0, errors
        
        # Basic validation: check if spec files are parseable
        for spec_file in spec_files:
            try:
                if spec_file.suffix in ['.yaml', '.yml']:
                    SchemaLoader.load_yaml(spec_file)
                elif spec_file.suffix == '.json':
                    SchemaLoader.load_json(spec_file)
                elif spec_file.suffix == '.md':
                    # Markdown spec - just check it exists and is readable
                    spec_file.read_text(encoding='utf-8')
            except Exception as e:
                errors.append(f"Spec file {spec_file.name} is invalid: {e}")
        
        # Additional criteria checks can be added here
        # e.g., "implementation_matches_spec" would require deeper analysis
        
        return len(errors) == 0, errors
