#!/usr/bin/env python3
"""
零配置快速启动模块

提供 Workflow.quick_start() 方法，无需任何配置即可开始使用工作流框架。
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import shutil

try:
    from .core.engine import WorkflowEngine
    from .bootstrap import get_template_dir, copy_template_files
except ImportError:
    # Fallback for direct execution
    try:
        from work_by_roles.core.engine import WorkflowEngine
    except ImportError:
        raise ImportError(
            "Cannot import WorkflowEngine. Please ensure work-by-roles is properly installed. "
            "Run: pip install -e ."
        )
    import importlib.util
    spec = importlib.util.spec_from_file_location("bootstrap", Path(__file__).parent / "bootstrap.py")
    if spec is None or spec.loader is None:
        raise ImportError("Failed to load bootstrap module")
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    get_template_dir = bootstrap.get_template_dir
    copy_template_files = bootstrap.copy_template_files


def detect_project_type(workspace: Path) -> str:
    """
    自动检测项目类型
    
    Returns:
        项目类型: 'web-app', 'api-service', 'cli-tool', 'minimal', 'standard_agile'
    """
    # 检查常见文件/目录
    if (workspace / "package.json").exists() or (workspace / "node_modules").exists():
        # 检查是否有前端框架
        if (workspace / "src" / "App.jsx").exists() or (workspace / "src" / "App.tsx").exists():
            return "web-app"
        elif (workspace / "server.js").exists() or (workspace / "server.ts").exists():
            return "api-service"
    
    if (workspace / "requirements.txt").exists() or (workspace / "pyproject.toml").exists():
        # Python项目
        if (workspace / "app.py").exists() or (workspace / "main.py").exists():
            # 检查是否有Flask/FastAPI
            try:
                with open(workspace / "requirements.txt", "r") as f:
                    content = f.read()
                    if "flask" in content.lower() or "fastapi" in content.lower():
                        return "api-service"
            except:
                pass
        
        # 检查是否有CLI入口
        if (workspace / "setup.py").exists() or (workspace / "pyproject.toml").exists():
            try:
                if (workspace / "pyproject.toml").exists():
                    import tomli
                    with open(workspace / "pyproject.toml", "rb") as f:
                        data = tomli.load(f)
                        if "project" in data and "scripts" in data.get("project", {}):
                            return "cli-tool"
            except:
                pass
    
    if (workspace / "go.mod").exists() or (workspace / "main.go").exists():
        return "api-service"
    
    if (workspace / "Cargo.toml").exists():
        return "cli-tool"
    
    # 默认返回标准敏捷模板
    return "standard_agile"


def auto_setup_workflow(workspace: Path, template: Optional[str] = None) -> Dict[str, Any]:
    """
    自动设置工作流配置
    
    Args:
        workspace: 工作空间路径
        template: 模板名称（如果为None，则自动检测）
    
    Returns:
        设置结果字典
    """
    workspace = Path(workspace).resolve()
    workflow_dir = workspace / ".workflow"
    workflow_dir.mkdir(exist_ok=True)
    temp_dir = workflow_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # 如果已存在配置，不覆盖
    if (workflow_dir / "workflow_schema.yaml").exists():
        return {
            "success": True,
            "message": "工作流配置已存在",
            "template": None,
            "workflow_dir": str(workflow_dir)
        }
    
    # 自动检测或使用指定模板
    if template is None:
        template = detect_project_type(workspace)
    
    # 确保模板存在
    template_dir = get_template_dir() / template
    if not template_dir.exists():
        # 回退到标准模板
        template = "standard_agile"
        template_dir = get_template_dir() / template
        if not template_dir.exists():
            # 最后回退到最小化模板
            template = "minimalist"
    
    # 复制模板文件
    try:
        copy_template_files(workspace, template)
        return {
            "success": True,
            "message": f"已使用模板 '{template}' 自动生成配置",
            "template": template,
            "workflow_dir": str(workflow_dir)
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"设置失败: {e}",
            "template": template,
            "workflow_dir": str(workflow_dir)
        }


class Workflow:
    """
    高级工作流API，提供简化的接口
    
    使用示例:
        from work_by_roles import Workflow
        
        # 零配置启动
        workflow = Workflow.quick_start()
        workflow.start("requirements")
    """
    
    def __init__(self, engine: WorkflowEngine):
        """初始化Workflow（内部使用）"""
        self.engine = engine
    
    @classmethod
    def quick_start(cls, workspace: Optional[Path] = None, template: Optional[str] = None) -> 'Workflow':
        """
        零配置快速启动
        
        自动检测项目类型，使用合适的模板生成配置，无需任何手动配置。
        
        Args:
            workspace: 工作空间路径（默认：当前目录）
            template: 模板名称（可选，默认自动检测）
        
        Returns:
            Workflow实例
        
        Example:
            >>> from work_by_roles import Workflow
            >>> workflow = Workflow.quick_start()
            >>> workflow.start("requirements")
        """
        workspace = Path(workspace or ".")
        workspace = workspace.resolve()
        
        # 自动设置工作流配置
        setup_result = auto_setup_workflow(workspace, template)
        if not setup_result["success"]:
            raise RuntimeError(f"快速启动失败: {setup_result['message']}")
        
        # 初始化引擎
        engine = WorkflowEngine(workspace)
        
        # 加载配置
        workflow_dir = workspace / ".workflow"
        skill_file = workflow_dir / "skills"  # Directory with Skill.md files
        roles_file = workflow_dir / "role_schema.yaml"
        workflow_file = workflow_dir / "workflow_schema.yaml"
        
        if not skill_file.is_dir() or not all(f.exists() for f in [roles_file, workflow_file]):
            raise RuntimeError(
                f"配置文件缺失。请确保以下文件/目录存在:\n"
                f"  - {skill_file} (目录，包含 Skill.md 文件)\n"
                f"  - {roles_file}\n"
                f"  - {workflow_file}"
            )
        
        engine.load_skill_library(skill_file)
        engine.load_roles(roles_file)
        engine.load_workflow(workflow_file)
        
        return cls(engine)
    
    @classmethod
    def from_template(cls, template: str, workspace: Optional[Path] = None) -> 'Workflow':
        """
        从指定模板创建Workflow
        
        Args:
            template: 模板名称（如 'web-app', 'api-service', 'cli-tool', 'minimalist'）
            workspace: 工作空间路径（默认：当前目录）
        
        Returns:
            Workflow实例
        """
        return cls.quick_start(workspace, template)
    
    def start(self, stage_id: str, role_id: Optional[str] = None) -> None:
        """
        启动阶段（自动推断角色）
        
        Args:
            stage_id: 阶段ID
            role_id: 角色ID（可选，如果不提供则从阶段定义中自动推断）
        """
        if role_id is None:
            # 自动推断角色
            stage = self.engine.executor._get_stage_by_id(stage_id) if self.engine.executor else None
            if stage:
                role_id = stage.role
            else:
                raise ValueError(f"无法推断角色，请明确指定: start('{stage_id}', '<role_id>')")
        
        self.engine.start_stage(stage_id, role_id)
    
    def complete(self, stage_id: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        完成阶段
        
        Args:
            stage_id: 阶段ID（可选，如果不提供则完成当前阶段）
        
        Returns:
            (是否通过, 错误列表)
        """
        if stage_id is None:
            current = self.engine.get_current_stage()
            if not current:
                raise ValueError("没有活动阶段，请先启动一个阶段")
            stage_id = current.id
        
        return self.engine.complete_stage(stage_id)
    
    def status(self) -> Dict[str, Any]:
        """获取工作流状态"""
        current = self.engine.get_current_stage()
        completed = self.engine.executor.get_completed_stages() if self.engine.executor else set()
        
        return {
            "current_stage": current.id if current else None,
            "current_stage_name": current.name if current else None,
            "current_role": self.engine.executor.state.current_role if self.engine.executor else None,
            "completed_stages": list(completed),
            "total_stages": len(self.engine.workflow.stages) if self.engine.workflow else 0
        }

