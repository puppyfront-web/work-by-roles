"""
Quality gate system for evaluating workflow stage quality gates.
Following Single Responsibility Principle - handles quality gate evaluation only.
"""

from typing import Dict, List, Callable, Any, Tuple
from pathlib import Path

from .exceptions import ValidationError
from .models import QualityGate, Stage
from .role_manager import RoleManager
from .schema_loader import SchemaLoader


class QualityGateSystem:
    """Manages quality gate evaluation with pluggable validators"""
    
    # Type alias for validator function signature
    ValidatorFunc = Callable[[Any, Stage, Path], Tuple[bool, List[str]]]
    
    def __init__(self, role_manager: RoleManager):
        self.role_manager = role_manager
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
    
    def _validate_completeness(self, gate: QualityGate, stage: Stage, workspace_path: Path) -> Tuple[bool, List[str]]:
        """Validate completeness of stage outputs"""
        errors = []
        for output in stage.outputs:
            # 文档类型输出生成到临时目录，避免侵入项目
            if output.type == "document" or output.type == "report":
                output_path = workspace_path / ".workflow" / "temp" / output.name
            else:
                output_path = workspace_path / output.name
            
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
                # 文档生成到临时目录
                doc_path = workspace_path / ".workflow" / "temp" / output.name
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

