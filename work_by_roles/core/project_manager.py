"""
Project manager for handling project initialization and configuration setup.
Following Single Responsibility Principle - handles project-level operations only.
"""

import shutil
import sys
import yaml
import warnings
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .exceptions import WorkflowError, ValidationError
from .project_scanner import ProjectScanner
from .workflow_engine import WorkflowEngine
from .role_manager import RoleManager
from .schema_loader import SchemaLoader
from .models import ProjectContext


class ProjectManager:
    """Manages project-level operations like initialization and setup"""
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)
        self.workflow_dir = self.workspace_path / ".workflow"
        self.temp_dir = self.workflow_dir / "temp"

    def ensure_workflow_dir(self) -> None:
        """Ensure .workflow directory and temp subdirectory exist"""
        self.workflow_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)

    def is_cursor_ide(self) -> bool:
        """Check if running inside Cursor IDE"""
        return os.environ.get('TERM_PROGRAM') == 'vscode' and 'cursor' in os.environ.get('PATH', '').lower()

    def get_shared_skills_dir(self) -> Optional[Path]:
        """Get shared skills directory if present"""
        shared_dir = self.workspace_path / "skills"
        if shared_dir.exists() and shared_dir.is_dir():
            return shared_dir
        return None

    def detect_project_type(self) -> str:
        """
        Automatically detect project type based on common files.
        
        Returns:
            Recommended template name
        """
        if (self.workspace_path / "package.json").exists() or (self.workspace_path / "node_modules").exists():
            if (self.workspace_path / "src" / "App.jsx").exists() or (self.workspace_path / "src" / "App.tsx").exists():
                return "web-app"
            elif (self.workspace_path / "server.js").exists() or (self.workspace_path / "server.ts").exists():
                return "api-service"
        
        if (self.workspace_path / "requirements.txt").exists() or (self.workspace_path / "pyproject.toml").exists():
            if (self.workspace_path / "app.py").exists() or (self.workspace_path / "main.py").exists():
                try:
                    with open(self.workspace_path / "requirements.txt", "r") as f:
                        content = f.read()
                        if "flask" in content.lower() or "fastapi" in content.lower():
                            return "api-service"
                except:
                    pass
            return "cli-tool"
        
        if (self.workspace_path / "go.mod").exists() or (self.workspace_path / "main.go").exists():
            return "api-service"
        
        if (self.workspace_path / "Cargo.toml").exists():
            return "cli-tool"
        
        return "standard_agile"

    def apply_template(self, template_dir: Path, shared_skills_dir: Optional[Path] = None) -> bool:
        """
        Setup project from a specific template.
        
        Returns:
            True if setup was successful, False if already initialized
        """
        self.ensure_workflow_dir()
        
        workflow_file = self.workflow_dir / "workflow_schema.yaml"
        roles_file = self.workflow_dir / "role_schema.yaml"
        skills_dir = self.workflow_dir / "skills"
        
        # Check if already initialized
        if workflow_file.exists() and roles_file.exists() and (skills_dir.exists() or (shared_skills_dir and shared_skills_dir.exists())):
            return False

        # Copy template files
        for f in template_dir.iterdir():
            if f.is_file() and f.suffix in ['.yaml', '.yml', '.md']:
                shutil.copy(f, self.workflow_dir / f.name)
            elif f.is_dir() and f.name == "skills":
                # Copy skills to .workflow/skills (default) or shared_skills_dir if provided
                if shared_skills_dir:
                    shutil.copytree(f, shared_skills_dir, dirs_exist_ok=True)
                else:
                    shutil.copytree(f, skills_dir, dirs_exist_ok=True)
        
        return True

    def scan_project(self) -> ProjectContext:
        """Scan project structure and return context"""
        scanner = ProjectScanner(self.workspace_path)
        context = scanner.scan()
        
        context_file = self.workflow_dir / "project_context.yaml"
        with open(context_file, 'w', encoding='utf-8') as f:
            yaml.dump(context.to_dict(), f, default_flow_style=False, allow_unicode=True)
            
        return context

    def setup_cursor_rules(self, engine: Optional[WorkflowEngine] = None) -> bool:
        """Generate or update .cursorrules file (deprecated - no longer generates rules)"""
        return False

    def generate_usage_guide(self) -> Path:
        """Generate USAGE.md file in .workflow directory"""
        usage_file = self.workflow_dir / "USAGE.md"
        usage_content = """# 快速使用指南

## ✅ 接入完成！

项目已成功接入 Multi-Role Skills Workflow 框架。

## 🚀 立即开始使用

### 方式 1: 在 Cursor IDE 中使用（推荐）

在 Cursor 的对话中直接使用：

```
@product_analyst 分析用户登录功能的需求
@system_architect 设计微服务架构
@core_framework_engineer 实现用户认证模块
@qa_reviewer 检查代码质量和测试覆盖率
```

或者使用 `@team` 触发完整工作流：

```
@team 实现用户登录功能
```

### 方式 2: 命令行使用

```bash
# 使用产品分析师角色分析需求
workflow role-execute product_analyst "分析用户登录功能的需求"

# 使用系统架构师角色设计架构
workflow role-execute system_architect "设计微服务架构"

# 使用核心框架工程师实现功能
workflow role-execute core_framework_engineer "实现用户认证模块"

# 使用QA审查员进行质量检查
workflow role-execute qa_reviewer "检查代码质量和测试覆盖率"
```

### 方式 3: 使用工作流（可选，适合大型项目）

```bash
# 查看可用角色
workflow list-roles

# 查看可用技能
workflow list-skills

# 启动工作流（如果配置了 workflow_schema.yaml）
workflow wfauto
```

## 📋 可用角色

运行 `workflow list-roles` 查看所有可用角色及其技能。

## 🛠️ 可用技能

运行 `workflow list-skills` 查看所有可用技能。

## 💡 提示

- **在 Cursor 中使用**: 使用 `@角色名` 或 `@team` 来让 AI 自动使用对应的角色和技能
- **自定义技能**: 使用 `workflow generate-skill` 创建新技能
- **自定义角色**: 编辑 `.workflow/role_schema.yaml` 添加新角色

## 📚 更多信息

查看项目文档了解更多功能：
- `README.md` - 完整文档
- `docs/CURSOR_GUIDE.md` - Cursor IDE 使用指南
- `docs/SKILLS_GUIDE.md` - 技能使用指南
- `docs/USAGE_GUIDE.md` - 使用指南
"""
        usage_file.write_text(usage_content, encoding='utf-8')
        return usage_file

    def initialize_state(self, roles_file: Path, workflow_file: Path, shared_skills_dir: Optional[Path] = None) -> WorkflowEngine:
        """Initialize engine and create initial state file"""
        skills_dir = self.workflow_dir / "skills"
        state_file = self.workflow_dir / "state.yaml"
        
        engine = WorkflowEngine(
            workspace_path=self.workspace_path,
            auto_save_state=True,
            state_file=state_file
        )
        
        # Load skill library
        if skills_dir.exists() and skills_dir.is_dir():
            engine.load_skill_library(skills_dir, shared_skills_dir=shared_skills_dir)
        elif shared_skills_dir:
            engine.load_skill_library(skills_dir, shared_skills_dir=shared_skills_dir)
            
        engine.load_roles(roles_file)
        engine.load_workflow(workflow_file)
        
        if not engine.executor:
            raise WorkflowError("Failed to create workflow executor")
            
        engine.save_state(state_file)
        
        # Auto-start first stage
        if engine.workflow and engine.workflow.stages:
            current_stage = engine.get_current_stage()
            if not current_stage:
                first_stage = min(engine.workflow.stages, key=lambda s: s.order)
                can_transition, _ = engine.executor.can_transition_to(first_stage.id)
                if can_transition:
                    try:
                        engine.start_stage(first_stage.id, first_stage.role)
                        engine.save_state(state_file)
                    except Exception as e:
                        warnings.warn(f"Failed to auto-start first stage: {e}")
        
        engine.update_vibe_context()
        self.setup_cursor_rules(engine)
        return engine
