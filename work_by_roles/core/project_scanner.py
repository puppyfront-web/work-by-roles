"""
Project scanner for discovering project structure and context.
Following Single Responsibility Principle - handles project scanning only.
"""

from pathlib import Path
from typing import Dict, Any
import json
import yaml

from .models import ProjectContext


class ProjectScanner:
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
        ]
        
        for pattern in spec_patterns:
            for spec_file in self.root_path.rglob(pattern):
                rel_path = str(spec_file.relative_to(self.root_path))
                # Use filename without extension as key
                key = spec_file.stem
                ctx.specs[key] = rel_path
                break  # Only take first match per pattern
        
        # 3. Scan Standards - look for common config files
        standard_files = {
            "package.json": "node",
            "requirements.txt": "python",
            "Pipfile": "python",
            "pyproject.toml": "python",
            "Cargo.toml": "rust",
            "go.mod": "go",
            "pom.xml": "java",
            "build.gradle": "java",
            ".eslintrc": "javascript",
            "tsconfig.json": "typescript",
        }
        
        for filename, tech in standard_files.items():
            file_path = self.root_path / filename
            if file_path.exists():
                ctx.standards[tech] = filename
        
        return ctx

