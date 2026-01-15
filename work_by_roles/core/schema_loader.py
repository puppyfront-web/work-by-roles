"""
Schema loader for loading and validating YAML/JSON files with security checks.
Following Single Responsibility Principle - handles schema loading only.
"""

from pathlib import Path
from typing import Dict, Any, cast
import json
import yaml

from .exceptions import ValidationError, SecurityError


def normalize_path(base: Path, relative_path: str) -> Path:
    """
    Normalize and validate a relative path to prevent path traversal attacks.
    
    Args:
        base: Base directory path
        relative_path: Relative path string
        
    Returns:
        Normalized absolute path
        
    Raises:
        SecurityError: If path traversal is detected
    """
    base_resolved = base.resolve()
    try:
        # Resolve the path
        target = (base / relative_path).resolve()
        
        # Check if resolved path is within base directory
        if not str(target).startswith(str(base_resolved)):
            raise SecurityError(
                f"Path traversal detected: '{relative_path}' resolves outside base directory '{base}'"
            )
        
        return target
    except (ValueError, OSError) as e:
        raise SecurityError(f"Invalid path: '{relative_path}': {e}")


class SchemaLoader:
    """Loads and validates schemas with security checks"""
    
    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    @staticmethod
    def _check_file_size(file_path: Path) -> None:
        """Check if file size is within limits"""
        try:
            size = file_path.stat().st_size
            if size > SchemaLoader.MAX_FILE_SIZE:
                raise SecurityError(
                    f"File '{file_path}' exceeds maximum size limit ({SchemaLoader.MAX_FILE_SIZE} bytes)"
                )
        except OSError as e:
            raise SecurityError(f"Cannot access file '{file_path}': {e}")
    
    @staticmethod
    def load_yaml(file_path: Path) -> Dict[str, Any]:
        """Load YAML file with security checks"""
        # Normalize path to prevent traversal
        normalized_path = normalize_path(file_path.parent, file_path.name)
        
        # Check file size
        SchemaLoader._check_file_size(normalized_path)
        
        try:
            with open(normalized_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                # Ensure we always return a dict for typing
                if not isinstance(data, dict):
                    raise ValidationError(
                        f"YAML root must be a mapping in {file_path}",
                        field="yaml",
                        context={"file": str(file_path)}
                    )
                return cast(Dict[str, Any], data)
        except yaml.YAMLError as e:
            raise ValidationError(
                f"Invalid YAML syntax in {file_path}: {e}",
                field="yaml",
                context={"file": str(file_path)}
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to load YAML from {file_path}: {e}",
                field="file",
                value=str(file_path)
            )
    
    @staticmethod
    def load_json(file_path: Path) -> Dict[str, Any]:
        """Load JSON file with security checks"""
        # Normalize path to prevent traversal
        normalized_path = normalize_path(file_path.parent, file_path.name)
        
        # Check file size
        SchemaLoader._check_file_size(normalized_path)
        
        try:
            with open(normalized_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    raise ValidationError(
                        f"JSON root must be an object in {file_path}",
                        field="json",
                        context={"file": str(file_path)}
                    )
                return cast(Dict[str, Any], data)
        except json.JSONDecodeError as e:
            raise ValidationError(
                f"Invalid JSON syntax in {file_path}: {e}",
                field="json",
                context={"file": str(file_path)}
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to load JSON from {file_path}: {e}",
                field="file",
                value=str(file_path)
            )
    
    @staticmethod
    def load_schema(file_path: Path) -> Dict[str, Any]:
        """Load schema file (YAML or JSON) with security checks"""
        if file_path.suffix in ['.yaml', '.yml']:
            return SchemaLoader.load_yaml(file_path)
        elif file_path.suffix == '.json':
            return SchemaLoader.load_json(file_path)
        else:
            raise ValidationError(
                f"Unsupported file format: {file_path.suffix}",
                field="format",
                value=file_path.suffix,
                context={"supported_formats": [".yaml", ".yml", ".json"]}
            )

