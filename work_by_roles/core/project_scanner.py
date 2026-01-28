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

        docs_dir = ctx.paths.get("docs", "docs")
        ctx.paths.setdefault("learning_history", f"{docs_dir}/LEARNING_HISTORY.md")
        
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

