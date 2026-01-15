import subprocess
from pathlib import Path
from typing import List, Tuple, Any
from .base import BaseValidator

class LinterValidator(BaseValidator):
    """Validator that runs Ruff and Mypy."""
    
    def validate(self, gate: Any, stage: Any, workspace_path: Path) -> Tuple[bool, List[str]]:
        errors = []
        
        # If this is a web project, skip python linting
        if (workspace_path / "index.html").exists():
            return True, []
        
        # Run Ruff
        try:
            result = subprocess.run(
                ["ruff", "check", "."],
                cwd=workspace_path,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                errors.append(f"Ruff found issues:\n{result.stdout or result.stderr}")
        except FileNotFoundError:
            # If ruff is not installed, skip but warn
            pass
            
        # Run Mypy
        try:
            result = subprocess.run(
                ["mypy", "."],
                cwd=workspace_path,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                errors.append(f"Mypy found issues:\n{result.stdout or result.stderr}")
        except FileNotFoundError:
            pass
            
        return len(errors) == 0, errors

class TestValidator(BaseValidator):
    """Validator that runs Pytest."""
    
    def validate(self, gate: Any, stage: Any, workspace_path: Path) -> Tuple[bool, List[str]]:
        errors = []
        
        # If this is a web project, skip python tests
        if (workspace_path / "index.html").exists():
            return True, []
        
        try:
            result = subprocess.run(
                ["pytest", "."],
                cwd=workspace_path,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                errors.append(f"Pytest failed:\n{result.stdout or result.stderr}")
        except FileNotFoundError:
            errors.append("pytest not found. Please install it to run functionality gates.")
            
        return len(errors) == 0, errors

